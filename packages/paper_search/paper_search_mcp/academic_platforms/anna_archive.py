"""Anna's Archive downloader - searches and downloads academic PDFs.

Strategy:
1. Search annas-archive.gl with DOI (SciDB) or title/PMID (general search).
2. Extract MD5 hash from search results.
3. Use Playwright to navigate to slow_download/{md5}/0/N, solve the DDoS-Guard
   JS challenge automatically, and save the PDF.

annas-archive.gl works without a bot challenge on the search/MD5 pages.
The slow_download endpoint requires a JS challenge, handled by Playwright.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Playwright is optional — fall back gracefully if not installed
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False
    logger.warning("playwright not installed; Anna's Archive slow_download unavailable")

_CHROMIUM_EXEC = os.environ.get("PAPER_SEARCH_MCP_PLAYWRIGHT_CHROMIUM", "").strip()


class AnnaArchiveFetcher:
    """PDF downloader using Anna's Archive (annas-archive.gl)."""

    MIRRORS = [
        "https://annas-archive.gl",
        "https://annas-archive.gs",
        "https://annas-archive.org",
    ]
    # Number of slow_download servers to try (0-based index)
    MAX_SLOW_SERVERS = 8

    def __init__(self, output_dir: str = "./downloads", base_url: str = ""):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.base_url = base_url.rstrip("/") if base_url else self._find_mirror()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_pdf(self, identifier: str) -> Optional[str]:
        """Download a PDF for a paper identified by DOI, title, or PMID.

        Strategy:
        1. If identifier looks like a DOI, use SciDB page which exposes a
           direct signed download URL (no DDoS-Guard, no login required).
        2. Otherwise, search for the paper, get the MD5, fetch the MD5 page,
           and extract any direct download URL from it.

        Args:
            identifier: DOI (preferred), paper title, or PMID.

        Returns:
            Absolute path to the saved PDF, or None on failure.
        """
        identifier = (identifier or "").strip()
        if not identifier:
            return None

        try:
            # Path A: DOI → SciDB direct download URL (fastest, most reliable)
            if re.match(r"10\.\d{4,9}/", identifier):
                result = self._download_via_scidb(identifier)
                if result:
                    return result

            # Path B: search → MD5 → MD5 page download URL
            md5 = self._resolve_md5(identifier)
            if not md5:
                logger.warning("Anna's Archive: no result for '%s'", identifier)
                return None

            logger.info("Anna's Archive: MD5=%s for '%s'", md5, identifier)
            result = self._download_via_md5_page(md5)
            if result:
                return result

            # Path C: Playwright fallback for slow_download (requires solved challenge)
            return self._download_via_playwright(md5)

        except Exception as exc:
            logger.error("Anna's Archive error for '%s': %s", identifier, exc)
            return None

    # ------------------------------------------------------------------
    # Direct download via SciDB (DOI-based, no auth required)
    # ------------------------------------------------------------------

    def _download_via_scidb(self, doi: str) -> Optional[str]:
        """Fetch SciDB page and download the direct signed URL it exposes."""
        scidb_url = f"{self.base_url}/scidb/{doi}"
        try:
            r = self.session.get(scidb_url, timeout=20)
            if r.status_code != 200:
                return None
            direct_url = self._extract_direct_download_url(r.text)
            if not direct_url:
                return None
            safe_doi = re.sub(r"[^\w.-]", "_", doi)
            return self._fetch_pdf(direct_url, f"scidb_{safe_doi}.pdf")
        except Exception as exc:
            logger.debug("SciDB direct download failed for %s: %s", doi, exc)
            return None

    def _download_via_md5_page(self, md5: str) -> Optional[str]:
        """Fetch MD5 page and try to download any direct URL present."""
        md5_url = f"{self.base_url}/md5/{md5}"
        try:
            r = self.session.get(md5_url, timeout=20)
            if r.status_code != 200:
                return None
            direct_url = self._extract_direct_download_url(r.text)
            if not direct_url:
                return None
            return self._fetch_pdf(direct_url, f"annasarchive_{md5}.pdf")
        except Exception as exc:
            logger.debug("MD5 page download failed for %s: %s", md5, exc)
            return None

    def _extract_direct_download_url(self, html: str) -> Optional[str]:
        """Find the signed direct-download URL (partner server, no auth) in HTML.

        Anna's Archive SciDB/MD5 pages embed a time-limited signed URL like:
        https://<random>.net/d3/x/<timestamp>/.../*.pdf
        These are accessible without DDoS-Guard or login.
        """
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Signed partner CDN URLs: match /d3/x/ path pattern
            if "/d3/x/" in href and href.endswith(".pdf"):
                return href
        return None

    def _fetch_pdf(self, url: str, filename: str) -> Optional[str]:
        """Download a PDF from url and save it to output_dir."""
        try:
            r = self.session.get(url, timeout=60, stream=True,
                                 headers={"Referer": self.base_url + "/"})
            if r.status_code != 200:
                logger.warning("Partner server returned HTTP %s for %s", r.status_code, url)
                return None
            content_type = r.headers.get("Content-Type", "")
            if "pdf" not in content_type:
                logger.warning("Partner server did not return PDF (Content-Type: %s)", content_type)
                return None
            out_path = self.output_dir / filename
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
            if out_path.stat().st_size < 1024:
                out_path.unlink(missing_ok=True)
                return None
            logger.info("Anna's Archive: saved %s (%d bytes)", out_path, out_path.stat().st_size)
            return str(out_path)
        except Exception as exc:
            logger.error("Fetch PDF failed for %s: %s", url, exc)
            return None

    # ------------------------------------------------------------------
    # Mirror detection
    # ------------------------------------------------------------------

    def _find_mirror(self) -> str:
        for mirror in self.MIRRORS:
            try:
                r = self.session.get(mirror, timeout=8)
                if r.status_code == 200 and len(r.text) > 1000:
                    logger.info("Anna's Archive: using mirror %s", mirror)
                    return mirror
            except Exception:
                continue
        logger.warning("Anna's Archive: no mirror responded, using %s", self.MIRRORS[0])
        return self.MIRRORS[0]

    # ------------------------------------------------------------------
    # MD5 resolution
    # ------------------------------------------------------------------

    def _resolve_md5(self, identifier: str) -> Optional[str]:
        """Try SciDB first (DOIs), then fall back to general search."""
        if re.match(r"10\.\d{4,9}/", identifier):
            md5 = self._scidb_lookup(identifier)
            if md5:
                return md5
        return self._search(identifier)

    def _scidb_lookup(self, doi: str) -> Optional[str]:
        """Use the SciDB endpoint for a precise DOI lookup."""
        url = f"{self.base_url}/scidb/{doi}"
        try:
            r = self.session.get(url, timeout=20)
            if r.status_code != 200:
                return None
            return self._extract_first_md5(r.text)
        except Exception as exc:
            logger.debug("SciDB lookup failed for %s: %s", doi, exc)
            return None

    def _search(self, query: str) -> Optional[str]:
        """General search on Anna's Archive."""
        url = f"{self.base_url}/search?q={quote(query)}&ext=pdf"
        try:
            r = self.session.get(url, timeout=20)
            if r.status_code != 200:
                return None
            return self._extract_first_md5(r.text)
        except Exception as exc:
            logger.debug("General search failed for '%s': %s", query, exc)
            return None

    @staticmethod
    def _extract_first_md5(html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/md5/" in href:
                md5 = href.split("/md5/")[-1].split("/")[0].split("?")[0]
                if re.fullmatch(r"[0-9a-fA-F]{32}", md5):
                    return md5
        return None

    # ------------------------------------------------------------------
    # Download via Playwright (solves DDoS-Guard JS challenge)
    # ------------------------------------------------------------------

    def _download_via_playwright(self, md5: str) -> Optional[str]:
        if not _HAS_PLAYWRIGHT:
            logger.error("playwright not available; cannot solve DDoS-Guard challenge")
            return None

        out_file = self.output_dir / f"annasarchive_{md5}.pdf"

        # Use a temp download dir so we can capture the file
        with tempfile.TemporaryDirectory() as tmp_dir:
            for server_idx in range(self.MAX_SLOW_SERVERS):
                dl_url = f"{self.base_url}/slow_download/{md5}/0/{server_idx}"
                logger.info("Trying slow_download server %d: %s", server_idx, dl_url)
                result = self._playwright_download(dl_url, tmp_dir)
                if result:
                    Path(result).rename(out_file)
                    logger.info("Anna's Archive: saved to %s", out_file)
                    return str(out_file)
                logger.debug("Server %d failed, trying next", server_idx)

        logger.warning("Anna's Archive: all %d slow servers failed for %s", self.MAX_SLOW_SERVERS, md5)
        return None

    def _playwright_download(self, url: str, download_dir: str) -> Optional[str]:
        """Open url in Playwright, solve DDoS-Guard JS challenge, then download."""
        import socket
        from urllib.parse import urlparse

        chromium_path = _CHROMIUM_EXEC if _CHROMIUM_EXEC and os.path.exists(_CHROMIUM_EXEC) else None

        # Resolve the hostname in Python (uses system DNS which works) and pass
        # to Chromium via --host-resolver-rules so Chromium doesn't fail with
        # its own DNS resolver.
        parsed = urlparse(self.base_url)
        hostname = parsed.hostname
        try:
            resolved_ip = socket.gethostbyname(hostname)
            resolver_rule = f"MAP {hostname} {resolved_ip}"
            logger.debug("DNS override: %s", resolver_rule)
        except Exception:
            resolver_rule = None

        try:
            with sync_playwright() as p:
                args = ["--no-sandbox", "--disable-dev-shm-usage"]
                if resolver_rule:
                    args.append(f"--host-resolver-rules={resolver_rule}")

                launch_kwargs: dict = {"headless": True, "args": args}
                if chromium_path:
                    launch_kwargs["executable_path"] = chromium_path

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()

                # Step 1: warm up session on main page so DDoS-Guard sets cookies
                page.goto(self.base_url + "/", timeout=30_000)
                page.wait_for_load_state("networkidle", timeout=15_000)

                # Step 2: navigate to download page; DDoS-Guard challenge runs here
                downloaded_file: list[str] = []

                def on_download(dl):
                    path = str(Path(download_dir) / (dl.suggested_filename or "paper.pdf"))
                    dl.save_as(path)
                    downloaded_file.append(path)

                context.on("download", on_download)
                page.goto(url, timeout=30_000)

                # Wait for challenge to pass and download to start (up to 45s)
                try:
                    page.wait_for_load_state("networkidle", timeout=45_000)
                except PWTimeout:
                    pass  # networkidle may never fire if download starts

                # Give download handler a moment to save the file
                import time
                deadline = time.time() + 10
                while not downloaded_file and time.time() < deadline:
                    time.sleep(0.5)

                browser.close()

                if downloaded_file and Path(downloaded_file[0]).exists():
                    size = Path(downloaded_file[0]).stat().st_size
                    if size > 1024:
                        return downloaded_file[0]
                    Path(downloaded_file[0]).unlink(missing_ok=True)

                return None

        except PWTimeout:
            logger.warning("Playwright timed out on %s", url)
            return None
        except Exception as exc:
            logger.error("Playwright error: %s", exc)
            return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a paper PDF via Anna's Archive")
    parser.add_argument("--doi", required=True, help="DOI, PMID, or title to resolve")
    parser.add_argument("--output", default="./downloads", help="Directory where the PDF will be saved")
    args = parser.parse_args()

    fetcher = AnnaArchiveFetcher(output_dir=args.output)
    result = fetcher.download_pdf(args.doi)
    if not result:
        raise SystemExit(1)
    print(result)


if __name__ == "__main__":
    main()
