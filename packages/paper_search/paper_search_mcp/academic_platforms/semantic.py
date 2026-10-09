from typing import List, Optional
from datetime import datetime
import requests
import time
import random
from ..paper import Paper
from ..utils import extract_doi
from .base import PaperSource
import logging
import re
from ..config import get_env

logger = logging.getLogger(__name__)


class SemanticSearcher(PaperSource):
    """Semantic Scholar paper search implementation"""

    SEMANTIC_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    SEMANTIC_BASE_URL = "https://api.semanticscholar.org/graph/v1"
    BROWSERS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    ]

    def __init__(self):
        self._setup_session()

    def _setup_session(self):
        """Initialize session with random user agent"""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": random.choice(self.BROWSERS),
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from Semantic Scholar format (e.g., '2025-06-02')"""
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return None

    def _extract_url_from_disclaimer(self, disclaimer: str) -> str:
        """Extract URL from disclaimer text"""
        # åŒ¹é…å¸¸è§çš„ URL æ¨¡å¼
        url_patterns = [
            r'https?://[^\s,)]+',  # åŸºæœ¬çš„ HTTP/HTTPS URL
            r'https?://arxiv\.org/abs/[^\s,)]+',  # arXiv é“¾æŽ¥
            r'https?://[^\s,)]*\.pdf',  # PDF æ–‡ä»¶é“¾æŽ¥
        ]

        all_urls = []
        for pattern in url_patterns:
            matches = re.findall(pattern, disclaimer)
            all_urls.extend(matches)

        if not all_urls:
            return ""

        doi_urls = [url for url in all_urls if 'doi.org' in url]
        if doi_urls:
            return doi_urls[0]

        non_unpaywall_urls = [url for url in all_urls if 'unpaywall.org' not in url]
        if non_unpaywall_urls:
            url = non_unpaywall_urls[0]
            if 'arxiv.org/abs/' in url:
                pdf_url = url.replace('/abs/', '/pdf/')
                return pdf_url
            return url

        if all_urls:
            url = all_urls[0]
            if 'arxiv.org/abs/' in url:
                pdf_url = url.replace('/abs/', '/pdf/')
                return pdf_url
            return url

        return ""

    def _parse_paper(self, item) -> Optional[Paper]:
        """Parse single paper entry from Semantic Scholar HTML and optionally fetch detailed info"""
        try:
            authors = [author['name'] for author in item.get('authors', [])]

            # Parse the publication date
            published_date = self._parse_date(item.get('publicationDate', ''))

            # Safely get PDF URL - æ”¯æŒä»Ž disclaimer ä¸­æå–
            pdf_url = ""
            if item.get('openAccessPdf'):
                open_access_pdf = item['openAccessPdf']
                # é¦–å…ˆå°è¯•ç›´æŽ¥èŽ·å– URL
                if open_access_pdf.get('url'):
                    pdf_url = open_access_pdf['url']
                # å¦‚æžœ URL ä¸ºç©ºä½†æœ‰ disclaimerï¼Œå°è¯•ä»Ž disclaimer ä¸­æå–
                elif open_access_pdf.get('disclaimer'):
                    pdf_url = self._extract_url_from_disclaimer(open_access_pdf['disclaimer'])

            # Safely get DOI
            doi = ""
            if item.get('externalIds') and item['externalIds'].get('DOI'):
                doi = item['externalIds']['DOI']

            if not doi and item.get('abstract'):
                doi = extract_doi(item['abstract'])

            # Safely get categories
            categories = item.get('fieldsOfStudy', [])
            if not categories:
                categories = []

            return Paper(
                paper_id=item['paperId'],
                title=item['title'],
                authors=authors,
                abstract=item.get('abstract', ''),
                url=item.get('url', ''),
                pdf_url=pdf_url,
                published_date=published_date,
                source="semantic",
                categories=categories,
                doi=doi,
                citations=item.get('citationCount', 0),
            )

        except Exception as e:
            logger.warning(f"Failed to parse Semantic paper: {e}")
            return None

    @staticmethod
    def get_api_key() -> Optional[str]:
        """
        Get the Semantic Scholar API key from environment variables.
        Returns None if no API key is set or if it's empty, enabling unauthenticated access.
        """
        api_key = get_env("SEMANTIC_SCHOLAR_API_KEY", "")
        if not api_key or api_key.strip() == "":
            logger.warning("No SEMANTIC_SCHOLAR_API_KEY set or it's empty. Using unauthenticated access with lower rate limits.")
            return None
        return api_key.strip()

    def request_api(self, path: str, params: dict) -> dict:
        """
        Make a request to the Semantic Scholar API with optional API key.
        """
        max_retries = 3
        api_key = self.get_api_key()
        retry_delay = 5 if api_key is None else 2
        has_retried_without_key = False

        for attempt in range(max_retries):
            try:
                headers = {"x-api-key": api_key} if api_key else {}
                url = f"{self.SEMANTIC_BASE_URL}/{path}"
                response = self.session.get(url, params=params, headers=headers, timeout=30)

                if response.status_code == 403 and api_key and not has_retried_without_key:
                    logger.warning("Semantic Scholar API key was rejected (403). Retrying without API key.")
                    api_key = None
                    has_retried_without_key = True
                    continue

                # æ£€æŸ¥æ˜¯å¦æ˜¯429é”™è¯¯ï¼ˆé™æµï¼‰
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        retry_after = response.headers.get("Retry-After")
                        wait_time = int(retry_after) if retry_after and retry_after.isdigit() else retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limited (429). Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limited (429) after {max_retries} attempts. Please wait before making more requests.")
                        return {"error": "rate_limited", "status_code": 429, "message": "Too many requests. Please wait before retrying."}

                response.raise_for_status()
                return response

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403 and api_key and not has_retried_without_key:
                    logger.warning("Semantic Scholar API key was rejected (403). Retrying without API key.")
                    api_key = None
                    has_retried_without_key = True
                    continue
                if e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        retry_after = e.response.headers.get("Retry-After")
                        wait_time = int(retry_after) if retry_after and retry_after.isdigit() else retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limited (429). Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limited (429) after {max_retries} attempts. Please wait before making more requests.")
                        return {"error": "rate_limited", "status_code": 429, "message": "Too many requests. Please wait before retrying."}
                else:
                    logger.error(f"HTTP Error requesting API: {e}")
                    return {"error": "http_error", "status_code": e.response.status_code, "message": str(e)}
            except Exception as e:
                logger.error(f"Error requesting API: {e}")
                return {"error": "general_error", "message": str(e)}

        return {"error": "max_retries_exceeded", "message": "Maximum retry attempts exceeded"}

    def search(
        self,
        query: str,
        year: Optional[str] = None,
        max_results: int = 10,
        fetch_details: bool = False,
    ) -> List[Paper]:
        """
        Search Semantic Scholar

        Args:
            query: Search query string
            year (Optional[str]): Filter by publication year. Supports several formats:
            - Single year: "2019"
            - Year range: "2016-2020"
            - Since year: "2010-"
            - Until year: "-2015"
            max_results: Maximum number of results to return
            fetch_details: Backward-compatible flag retained for older callers.
                Semantic search responses already include the fields this connector uses,
                so the current implementation does not perform extra per-paper detail fetches.

        Returns:
            List[Paper]: List of paper objects
        """
        papers = []

        try:
            fields = [
                "title",
                "abstract",
                "year",
                "citationCount",
                "authors",
                "url",
                "publicationDate",
                "externalIds",
                "fieldsOfStudy",
                "openAccessPdf",
            ]
            # Construct search parameters
            params = {
                "query": query,
                "limit": max_results,
                "fields": ",".join(fields),
            }
            if year:
                params["year"] = year
            # Make request
            response = self.request_api("paper/search", params)

            # Check for errors
            if isinstance(response, dict) and "error" in response:
                error_msg = response.get("message", "Unknown error")
                if response.get("error") == "rate_limited":
                    logger.error(f"Rate limited by Semantic Scholar API: {error_msg}")
                else:
                    logger.error(f"Semantic Scholar API error: {error_msg}")
                return papers

            # Check response status code
            if not hasattr(response, 'status_code') or response.status_code != 200:
                status_code = getattr(response, 'status_code', 'unknown')
                logger.error(f"Semantic Scholar search failed with status {status_code}")
                return papers

            data = response.json()
            results = data['data']

            if not results:
                logger.info("No results found for the query")
                return papers

            # Process each result
            for i, item in enumerate(results):
                if len(papers) >= max_results:
                    break

                logger.info(f"Processing paper {i+1}/{min(len(results), max_results)}")
                paper = self._parse_paper(item)
                if paper:
                    papers.append(paper)

        except Exception as e:
            logger.error(f"Semantic Scholar search error: {e}")

        return papers[:max_results]

if __name__ == "__main__":
    # Test Semantic searcher
    searcher = SemanticSearcher()

    print("Testing Semantic search functionality...")
    query = "secret sharing"
    max_results = 2

    print("\n" + "=" * 60)
    print("1. Testing search with detailed information")
    print("=" * 60)
    try:
        papers = searcher.search(query, year=None, max_results=max_results)
        print(f"\nFound {len(papers)} papers for query '{query}' (with details):")
        for i, paper in enumerate(papers, 1):
            print(f"\n{i}. {paper.title}")
            print(f"   Paper ID: {paper.paper_id}")
            print(f"   Authors: {', '.join(paper.authors)}")
            print(f"   Categories: {', '.join(paper.categories)}")
            print(f"   URL: {paper.url}")
            if paper.pdf_url:
                print(f"   PDF: {paper.pdf_url}")
            if paper.published_date:
                print(f"   Published Date: {paper.published_date}")
            if paper.abstract:
                print(f"   Abstract: {paper.abstract[:200]}...")
    except Exception as e:
        print(f"Error during detailed search: {e}")

    print("\n" + "=" * 60)
    print("2. Testing manual paper details fetching")
    print("=" * 60)
    test_paper_id = "5bbfdf2e62f0508c65ba6de9c72fe2066fd98138"
    try:
        paper_details = searcher.get_paper_details(test_paper_id)
        if paper_details:
            print(f"\nManual fetch for paper {test_paper_id}:")
            print(f"Title: {paper_details.title}")
            print(f"Authors: {', '.join(paper_details.authors)}")
            print(f"Categories: {', '.join(paper_details.categories)}")
            print(f"URL: {paper_details.url}")
            if paper_details.pdf_url:
                print(f"PDF: {paper_details.pdf_url}")
            if paper_details.published_date:
                print(f"Published Date: {paper_details.published_date}")
            print(f"DOI: {paper_details.doi}")
            print(f"Citations: {paper_details.citations}")
            print(f"Abstract: {paper_details.abstract[:200]}...")
        else:
            print(f"Could not fetch details for paper {test_paper_id}")
    except Exception as e:
        print(f"Error fetching paper details: {e}")
