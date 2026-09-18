#!/usr/bin/env python3
"""Search, enrich, and download papers for a topic with minimal agent overhead."""

from __future__ import annotations

import argparse
from hashlib import md5
import json
import logging
import multiprocessing as mp
import os
import re
import sys
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from requests.exceptions import SSLError

from paper_search_mcp.academic_platforms.europepmc import EuropePMCSearcher
from paper_search_mcp.academic_platforms.openalex import OpenAlexSearcher
from paper_search_mcp.academic_platforms.pubmed import PubMedSearcher
from paper_search_mcp.academic_platforms.crossref import CrossRefSearcher
from paper_search_mcp.academic_platforms.semantic import SemanticSearcher
from paper_search_mcp.academic_platforms.unpaywall import UnpaywallResolver
from paper_search_mcp.paper import Paper

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SEARCHER_FACTORIES: dict[str, Callable[[], Any]] = {
    "pubmed": PubMedSearcher,
    "europepmc": EuropePMCSearcher,
    "openalex": OpenAlexSearcher,
    "semantic": SemanticSearcher,
    "crossref": CrossRefSearcher,
}

IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
DEFAULT_SOURCES = "pubmed,europepmc,openalex,semantic,crossref"
REQUEST_TIMEOUT = 30
ANNA_TIMEOUT_SECONDS = int(os.environ.get("PAPER_SEARCH_MCP_ANNA_TIMEOUT_SECONDS", "120"))
_UNPAYWALL_RESOLVER: UnpaywallResolver | None = None
ANNA_SOURCE = "anna_archive"
MIN_PDF_BYTES = 1024
DOWNLOAD_HEADERS = {
    "User-Agent": "EZresearchLM/0.1 (+https://github.com/openags/paper-search-mcp)",
    "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
}
logger = logging.getLogger(__name__)


def normalize_doi(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"^(doi:)\s*", "", text)
    return text.strip().rstrip(".")


def normalize_identifier(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    doi = normalize_doi(text)
    if doi.startswith("10."):
        return f"DOI:{doi}"
    if upper.startswith("PMID:"):
        return f"PMID:{upper.split(':', 1)[1].strip()}"
    if upper.startswith("PMCID:"):
        return f"PMCID:{upper.split(':', 1)[1].strip().upper()}"
    if upper.startswith("PMC"):
        return f"PMCID:{upper}"
    if text.isdigit():
        return f"PMID:{text}"
    return f"TITLE:{normalize_title(text)}"


def record_identifiers(record: dict[str, Any]) -> set[str]:
    identifiers = set()
    for key in ("doi", "pmid", "pmcid"):
        value = record.get(key)
        if value:
            identifiers.add(normalize_identifier(str(value)))
    title = normalize_title(record.get("title") or "")
    if title:
        identifiers.add(f"TITLE:{title}")
    return identifiers


def load_target_file(path: str | None) -> dict[str, Any]:
    if not path:
        return {"must_have": [], "nice_to_have": [], "allow_anna_fallback": False}
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return {"must_have": payload, "nice_to_have": [], "allow_anna_fallback": False}
    if not isinstance(payload, dict):
        raise SystemExit("ERROR: --must-have-file must contain a JSON object or array")
    return {
        "must_have": payload.get("must_have") or [],
        "nice_to_have": payload.get("nice_to_have") or [],
        "allow_anna_fallback": bool(payload.get("allow_anna_fallback")),
    }


def target_to_entry(target: Any, required: bool) -> dict[str, Any]:
    if isinstance(target, str):
        target_id = normalize_identifier(target)
        return {
            "target_id": target_id,
            "raw_target": target,
            "title": target if target_id.startswith("TITLE:") else "",
            "doi": target_id.split(":", 1)[1] if target_id.startswith("DOI:") else "",
            "pmid": target_id.split(":", 1)[1] if target_id.startswith("PMID:") else "",
            "pmcid": target_id.split(":", 1)[1] if target_id.startswith("PMCID:") else "",
            "required": required,
        }
    if isinstance(target, dict):
        raw = target.get("target_id") or target.get("doi") or target.get("pmid") or target.get("pmcid") or target.get("title") or ""
        target_id = normalize_identifier(raw)
        return {
            "target_id": target_id,
            "raw_target": raw,
            "title": target.get("title") or (raw if target_id.startswith("TITLE:") else ""),
            "doi": normalize_doi(target.get("doi")) if target.get("doi") else (target_id.split(":", 1)[1] if target_id.startswith("DOI:") else ""),
            "pmid": str(target.get("pmid") or (target_id.split(":", 1)[1] if target_id.startswith("PMID:") else "")),
            "pmcid": str(target.get("pmcid") or (target_id.split(":", 1)[1] if target_id.startswith("PMCID:") else "")),
            "required": required,
        }
    raise SystemExit("ERROR: must_have/nice_to_have entries must be strings or objects")


def normalize_targets(config: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [target_to_entry(item, True) for item in config.get("must_have") or []]
    entries.extend(target_to_entry(item, False) for item in config.get("nice_to_have") or [])
    return entries


def target_discovery_queries(targets: list[dict[str, Any]]) -> list[str]:
    queries: list[str] = []
    for target in targets:
        for key in ("doi", "pmid", "pmcid"):
            value = str(target.get(key) or "").strip()
            if value:
                queries.append(value)
        title = str(target.get("title") or "").strip()
        if title:
            queries.append(title)
    unique: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(query)
    return unique


def discovery_queries(user_queries: list[str], targets: list[dict[str, Any]]) -> list[str]:
    exact = target_discovery_queries(targets)
    combined = exact + user_queries
    unique: list[str] = []
    seen: set[str] = set()
    for query in combined:
        key = query.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(query.strip())
    return unique


def target_matches_record(target: dict[str, Any], record: dict[str, Any]) -> bool:
    identifiers = record_identifiers(record)
    target_id = target.get("target_id") or ""
    if target_id in identifiers:
        return True
    target_title = normalize_title(target.get("title") or "")
    record_title = normalize_title(record.get("title") or "")
    return bool(target_title and record_title and (target_title == record_title or target_title in record_title or record_title in target_title))


def normalize_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slugify_fragment(text: str, default: str = "paper", max_words: int = 8) -> str:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    if not words:
        return default
    return "_".join(words[:max_words])


def parse_queries(raw: str) -> list[str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: --queries must be a JSON array of strings: {exc}") from exc

    if not isinstance(payload, list) or not payload or any(not isinstance(item, str) for item in payload):
        raise SystemExit("ERROR: --queries must be a non-empty JSON array of strings")
    return [item.strip() for item in payload if item.strip()]


def parse_sources(raw: str) -> list[str]:
    sources = [item.strip().lower() for item in (raw or DEFAULT_SOURCES).split(",") if item.strip()]
    invalid = [source for source in sources if source not in SEARCHER_FACTORIES]
    if invalid:
        raise SystemExit(f"ERROR: unsupported sources: {', '.join(invalid)}")
    return sources


def year_from_paper(paper: Paper) -> int | None:
    if paper.published_date:
        return paper.published_date.year
    return None


def extract_ids(paper: Paper) -> tuple[str | None, str | None]:
    pmid = None
    pmcid = None
    extra = paper.extra or {}

    candidates = [
        extra.get("pmid"),
        extra.get("pmcid"),
        paper.paper_id,
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if not value:
            continue
        if value.upper().startswith("PMID:"):
            pmid = value.split(":", 1)[1]
        elif value.upper().startswith("PMC"):
            pmcid = value.upper()
        elif value.isdigit():
            if paper.source == "pubmed" or not pmid:
                pmid = value
    return pmid, pmcid


def record_from_paper(paper: Paper, query: str, source: str) -> dict[str, Any]:
    pmid, pmcid = extract_ids(paper)
    authors = "; ".join(paper.authors) if paper.authors else ""
    year = year_from_paper(paper)
    url = paper.url or ""
    return {
        "title": paper.title,
        "authors": authors,
        "year": year,
        "doi": (paper.doi or "").strip(),
        "pmid": pmid,
        "pmcid": pmcid,
        "abstract": paper.abstract or "",
        "url": url,
        "pdf_url": (paper.pdf_url or "").strip() or None,
        "tgz_url": None,
        "is_oa": bool(paper.pdf_url),
        "pdf_path": None,
        "pdf_status": None,
        "pdf_source": None,
        "oa_sources": [],
        "manual_reason": None,
        "source": source,
        "sources": [source],
        "queries": [query],
        "paper_id": paper.paper_id,
        "identifier_confidence": 0,
        "title_match_confidence": 0,
        "source_match_reason": "",
        "acquisition_policy": "oa_first",
        "fallback_after": [],
    }


def score_record_confidence(record: dict[str, Any], targets: list[dict[str, Any]]) -> dict[str, Any]:
    identifiers = record_identifiers(record)
    record["identifier_confidence"] = 80 if any(item.startswith(("DOI:", "PMID:", "PMCID:")) for item in identifiers) else 30
    record["title_match_confidence"] = 0
    record["source_match_reason"] = "discovery_result"
    for target in targets:
        if target.get("target_id") in identifiers:
            record["identifier_confidence"] = 100
            record["title_match_confidence"] = 100
            record["source_match_reason"] = f"matched_target:{target.get('target_id')}"
            return record
        target_title = normalize_title(target.get("title") or "")
        record_title = normalize_title(record.get("title") or "")
        if target_title and record_title:
            if target_title == record_title:
                record["title_match_confidence"] = max(record["title_match_confidence"], 100)
                record["source_match_reason"] = "exact_title_match"
            elif target_title in record_title or record_title in target_title:
                record["title_match_confidence"] = max(record["title_match_confidence"], 75)
                record["source_match_reason"] = "partial_title_match"
    return record


def target_priority(record: dict[str, Any], targets: list[dict[str, Any]]) -> int:
    for target in targets:
        if target.get("required") and target_matches_record(target, record):
            return 0
    for target in targets:
        if target_matches_record(target, record):
            return 1
    return 2


def availability_status(record: dict[str, Any]) -> str:
    """Report access separately from bibliographic relevance."""
    if record.get("pdf_status") == "downloaded" or record.get("pdf_path"):
        return "open_full_text"
    if record.get("pdf_status") == "candidate":
        return "candidate"
    if record.get("pdf_status") == "manual_needed":
        return "paywalled_or_unresolved"
    if record.get("is_oa") or record.get("pdf_url") or record.get("tgz_url"):
        return "open_full_text_candidate"
    if record.get("abstract"):
        return "abstract_only"
    return "metadata_only"


def review_priority(record: dict[str, Any], targets: list[dict[str, Any]]) -> str:
    """Classify rescue urgency without treating OA as scientific quality."""
    priority = target_priority(record, targets)
    if priority == 0:
        return "must_have"
    if priority == 1:
        return "nice_to_have"
    if len(record.get("sources") or []) >= 2:
        return "high_priority"
    if record.get("abstract"):
        return "candidate"
    return "low_priority"


def metadata_score(record: dict[str, Any]) -> int:
    return sum(
        1
        for key in ("title", "authors", "year", "doi", "pmid", "pmcid", "abstract", "url", "pdf_url", "tgz_url")
        if record.get(key)
    )


def merge_records(best: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if metadata_score(candidate) > metadata_score(best):
        primary, secondary = candidate.copy(), best
    else:
        primary, secondary = best.copy(), candidate

    for field in ("doi", "pmid", "pmcid", "abstract", "url", "pdf_url", "tgz_url", "year", "authors", "paper_id"):
        if not primary.get(field) and secondary.get(field):
            primary[field] = secondary[field]

    primary["is_oa"] = bool(primary.get("is_oa") or secondary.get("is_oa"))
    primary["oa_sources"] = sorted(set((primary.get("oa_sources") or []) + (secondary.get("oa_sources") or [])))
    primary["sources"] = sorted(set((primary.get("sources") or []) + (secondary.get("sources") or [])))
    primary["queries"] = sorted(set((primary.get("queries") or []) + (secondary.get("queries") or [])))
    primary['pdf_urls'] = list(dict.fromkeys(u for item in (primary, secondary)
                                           for u in [item.get('pdf_url'), *(item.get('pdf_urls') or [])] if u))
    primary["source"] = primary["sources"][0] if primary["sources"] else primary.get("source")
    return primary


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    for record in records:
        record['doi'] = normalize_doi(record.get('doi'))
        match = next((i for i, previous in enumerate(grouped) if same_identity(previous, record)), None)
        if match is None:
            grouped.append(record)
        else:
            grouped[match] = merge_records(grouped[match], record)
    return grouped


def same_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Exact stable identifiers, never contradictory IDs or title-only similarity."""
    ids = ('doi', 'pmid', 'pmcid')
    def value(row, key):
        return normalize_doi(row.get(key)) if key == 'doi' else str(row.get(key) or '').lower().strip()
    shared = [key for key in ids if value(left, key) and value(right, key)]
    if shared:
        return all(value(left, key) == value(right, key) for key in shared)
    if any(value(row, key) for row in (left, right) for key in ids):
        return False
    fields = ('title', 'year', 'authors')
    return all(left.get(key) and right.get(key) and normalize_title(str(left[key])) == normalize_title(str(right[key])) for key in fields)


def fetch_oa_metadata(pmid: str | None, pmcid: str | None) -> dict[str, Any]:
    session = requests.Session()
    resolved_pmcid = (pmcid or "").strip().upper() or None
    pdf_url = None
    tgz_url = None
    cloud_metadata = None
    attempts = []

    if pmid and not resolved_pmcid:
        try:
            response = session.get(IDCONV_URL, params={"ids": pmid, "format": "json"}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            records = response.json().get("records", [])
            if records:
                resolved_pmcid = str(records[0].get("pmcid") or "").strip().upper() or None
        except Exception:
            pass

    if resolved_pmcid:
        try:
            from ez.acquisition import Retriever
            from ez.pmc import locations as pmc_locations
            with tempfile.TemporaryDirectory() as folder:
                retriever = Retriever(folder, 'legacy-pmc', seconds=60, attempts=1)
                candidates = pmc_locations(retriever, {'pmcid': resolved_pmcid})
                # Legacy has no per-version selection contract: do not choose
                # between multiple PMC versions on the user's behalf.
                if len(candidates) == 1:
                    selected = retriever.location_metadata[candidates[0][0]]
                    if not selected.get('requires_version_review') and not selected.get('is_retracted'):
                        pdf_url = candidates[0][0]
                        cloud_metadata = selected
                attempts = retriever.history
        except Exception:
            pass

    return {
        "pmcid": resolved_pmcid,
        "pdf_url": pdf_url,
        "tgz_url": tgz_url,
        "is_oa": bool(pdf_url or tgz_url),
        "pmc_cloud_metadata": cloud_metadata,
        "pmc_resolution_attempts": attempts,
    }


def get_unpaywall_resolver() -> UnpaywallResolver:
    global _UNPAYWALL_RESOLVER
    if _UNPAYWALL_RESOLVER is None:
        _UNPAYWALL_RESOLVER = UnpaywallResolver()
    return _UNPAYWALL_RESOLVER


def fetch_unpaywall_pdf_url(doi: str | None) -> str | None:
    doi = (doi or "").strip()
    if not doi:
        return None
    resolver = get_unpaywall_resolver()
    if not resolver.has_api_access():
        return None
    return resolver.resolve_best_pdf_url(doi)


def normalize_ftp_url(url: str) -> str:
    return (url or "").replace("ftp://ftp.ncbi.nlm.nih.gov", "https://ftp.ncbi.nlm.nih.gov")


def safe_tar_extract(archive: tarfile.TarFile, destination: Path) -> None:
    base = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if not str(target).startswith(str(base)):
            raise ValueError(f"Unsafe tar member path: {member.name}")
    try:
        archive.extractall(destination, filter="data")
    except TypeError:
        archive.extractall(destination)


def filename_for_record(record: dict[str, Any]) -> str:
    first_author = "paper"
    authors = (record.get("authors") or "").split(";")
    if authors and authors[0].strip():
        first_author = slugify_fragment(authors[0].split()[0], default="paper", max_words=2)
    year = str(record.get("year") or "unknown")
    title_part = slugify_fragment(record.get("title") or "", default="untitled", max_words=8)
    return f"{first_author}_{year}_{title_part}.pdf"


def looks_like_pdf(data: bytes) -> bool:
    return bool(data) and data.lstrip().startswith(b"%PDF")


def valid_pdf_file(path: Path, min_bytes: int = 0) -> bool:
    if not path.exists() or path.stat().st_size < min_bytes:
        return False
    from ez.pdf import validate_pdf_bounded
    return validate_pdf_bounded(path)['status'] == 'valid'


def _anna_download_worker(identifier: str, save_dir: str, queue: Any) -> None:
    try:
        from paper_search_mcp.academic_platforms.anna_archive import AnnaArchiveFetcher

        fetcher = AnnaArchiveFetcher(output_dir=save_dir)
        queue.put({"path": fetcher.download_pdf(identifier)})
    except BaseException as exc:
        queue.put({"error": f"{type(exc).__name__}: {exc}"})


def download_anna_identifier_with_timeout(identifier: str, save_dir: Path, timeout_seconds: int = ANNA_TIMEOUT_SECONDS) -> tuple[str | None, str]:
    if timeout_seconds <= 0:
        timeout_seconds = ANNA_TIMEOUT_SECONDS
    try:
        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
        process = ctx.Process(target=_anna_download_worker, args=(identifier, str(save_dir), queue))
        process.daemon = True
        process.start()
        process.join(timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(5)
            return None, "timeout"
        if queue.empty():
            return None, "failed"
        payload = queue.get_nowait()
    except Exception:
        return None, "failed"

    path = payload.get("path") if isinstance(payload, dict) else None
    if path:
        return str(path), "downloaded"
    return None, "failed"


def pdf_source_for_record(record: dict[str, Any]) -> str:
    sources = set(record.get("oa_sources") or [])
    if "unpaywall" in sources:
        return "unpaywall"
    if "pmc-oa" in sources:
        return "pmc_oa"
    record_sources = set(record.get("sources") or [])
    if record_sources.intersection({"europepmc", "openalex"}):
        return "europepmc_openalex"
    return "direct"


def candidate_download_urls(url: str) -> list[str]:
    """Return equivalent source-native URLs worth trying before rescue."""
    raw = (url or "").strip()
    if not raw:
        return []

    candidates = [raw]
    parsed = urlparse(raw)
    if parsed.scheme == "http":
        candidates.append("https://" + raw[len("http://"):])

    # PBMC's Unpaywall URL is sometimes http://.../PBMC-... while the working
    # public PDF is served over HTTPS from the same path, occasionally with an
    # -en suffix. Try both before marking the source manual_needed.
    if parsed.netloc.lower() == "pbmc.ibmc.msk.ru" and not parsed.path.endswith("-en"):
        candidates.append(raw + "-en")
        if parsed.scheme == "http":
            candidates.append("https://" + raw[len("http://"):] + "-en")

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _download_response(url: str) -> requests.Response:
    # A PDF signature cannot establish the authenticity of a TLS peer.
    return requests.get(url, timeout=90, stream=True, headers=DOWNLOAD_HEADERS)


def download_binary(url: str, destination: Path, expected: str | None = None, expected_md5: str | None = None) -> bool:
    started = time.monotonic()
    response = _download_response(url)
    temporary = destination.with_suffix(destination.suffix + '.part')
    try:
        response.raise_for_status()
        size = 0
        with temporary.open('wb') as handle:
            for chunk in response.iter_content(65536):
                if not chunk:
                    continue
                if not size and expected == 'pdf' and not looks_like_pdf(chunk):
                    return False
                size += len(chunk)
                if size > 100 * 1024 * 1024 or time.monotonic() - started > 120:
                    return False
                handle.write(chunk)
        if not size or (expected == 'pdf' and not valid_pdf_file(temporary)):
            return False
        if expected_md5 and md5(temporary.read_bytes()).hexdigest() != expected_md5:
            return False
        os.replace(temporary, destination)
        return True
    finally:
        response.close()
        temporary.unlink(missing_ok=True)


def try_anna_archive(record: dict[str, Any], save_dir: Path) -> tuple[str | None, str]:
    identifiers = [
        normalize_doi(record.get("doi")),
        str(record.get("pmid") or "").strip(),
        record.get("title") or "",
    ]
    identifiers = [item for item in identifiers if item]
    if not identifiers:
        return None, "no_identifier"
    for identifier in identifiers:
        path, status = download_anna_identifier_with_timeout(identifier, save_dir)
        if path and valid_pdf_file(Path(path)):
            return path, "downloaded"
        if status == "timeout":
            return None, "timeout"
    return None, "failed"


def extract_pdf_from_tgz(url: str, destination: Path, record=None) -> bool:
    from ez.acquisition import archive_pdf
    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "paper.tgz"
        if not download_binary(url, archive_path):
            return False
        payload = archive_pdf(archive_path.read_bytes(), record or {})
        candidate = Path(tmp_dir) / 'candidate.pdf'
        candidate.write_bytes(payload)
        if not valid_pdf_file(candidate):
            return False
        os.replace(candidate, destination)
        return True


def try_direct_pdf(record: dict[str, Any], save_dir: Path) -> tuple[str | None, str]:
    pdf_url = normalize_ftp_url(record.get("pdf_url") or "")
    tgz_url = normalize_ftp_url(record.get("tgz_url") or "")
    destination = save_dir / filename_for_record(record)
    for candidate_url in candidate_download_urls(pdf_url):
        try:
            checksum = (record.get('pmc_cloud_metadata') or {}).get('expected_md5')
            options = {'expected_md5': checksum} if checksum and candidate_url.startswith('https://pmc-oa-opendata.s3.amazonaws.com/') else {}
            if download_binary(candidate_url, destination, expected="pdf", **options):
                return str(destination), "downloaded"
        except Exception as exc:
            logger.debug("Direct PDF download failed for %s: %s", candidate_url, exc)

    try:
        if tgz_url and extract_pdf_from_tgz(tgz_url, destination, record):
            return str(destination), "downloaded"
    except Exception as exc:
        logger.debug("TGZ PDF extraction failed for %s: %s", tgz_url, exc)

    return None, "failed"


def search_single(source: str, query: str, max_results: int) -> list[dict[str, Any]]:
    searcher = SEARCHER_FACTORIES[source]()
    papers = searcher.search(query, max_results=max_results)
    return [record_from_paper(paper, query, source) for paper in papers]


def run_searches(queries: list[str], sources: list[str], max_results: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    max_workers = max(1, min(8, len(queries) * len(sources)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(search_single, source, query, max_results): (source, query)
            for source in sources
            for query in queries
        }
        for future in as_completed(futures):
            source, query = futures[future]
            try:
                results.extend(future.result())
            except Exception as exc:
                print(f"WARNING: {source} failed for '{query}': {exc}", file=sys.stderr)
    return results


def enrich_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for record in records:
        record.setdefault("oa_sources", [])
        oa = fetch_oa_metadata(record.get("pmid"), record.get("pmcid"))
        if oa.get('pmc_cloud_metadata'):
            record['pmc_cloud_metadata'] = oa['pmc_cloud_metadata']
        if oa.get('pmc_resolution_attempts'):
            record['pmc_resolution_attempts'] = oa['pmc_resolution_attempts']
        if oa.get("pmcid") and not record.get("pmcid"):
            record["pmcid"] = oa["pmcid"]
        if oa.get("pdf_url"):
            record["pdf_url"] = oa["pdf_url"]
        if oa.get("tgz_url"):
            record["tgz_url"] = oa["tgz_url"]
        if oa.get("is_oa"):
            record["is_oa"] = True
            record["oa_sources"] = sorted(set((record.get("oa_sources") or []) + ["pmc-oa"]))

        if not record.get("pdf_url"):
            unpaywall_url = fetch_unpaywall_pdf_url(record.get("doi"))
            if unpaywall_url:
                record["pdf_url"] = unpaywall_url
                record["is_oa"] = True
                record["oa_sources"] = sorted(set((record.get("oa_sources") or []) + ["unpaywall"]))

        if record.get("pdf_url"):
            host = urlparse(record["pdf_url"]).netloc.lower()
            if host:
                record["is_oa"] = True
    return records


def download_for_record(record: dict[str, Any], save_dir: Path, min_oa: bool, allow_anna_fallback: bool = False) -> dict[str, Any]:
    record["pdf_status"] = "no_pdf"
    record["pdf_path"] = None
    record["pdf_source"] = None
    record["manual_reason"] = None
    record["acquisition_policy"] = "oa_first"
    record["fallback_after"] = []
    record["acquisition_attempts"] = []

    if record.get("is_oa") or record.get("pdf_url") or record.get("tgz_url"):
        path, status = try_direct_pdf(record, save_dir)
        record["acquisition_attempts"].append({"provider": "legacy_direct_or_pmc", "result": status})
        if path:
            record["pdf_path"] = path
            record["pdf_status"] = status
            record["pdf_source"] = pdf_source_for_record(record)
            return record
        if status == "failed":
            record["pdf_status"] = "failed"

    if allow_anna_fallback and (record.get("doi") or record.get("pmid") or record.get("title")):
        path, status = try_anna_archive(record, save_dir)
        record["fallback_after"] = [attempt["provider"] for attempt in record["acquisition_attempts"]]
        if path:
            record["pdf_path"] = path
            record["pdf_status"] = "downloaded"
            record["pdf_source"] = ANNA_SOURCE
            record["acquisition_policy"] = "non_oa_fallback"
            provenance_path = Path(str(path) + ".provenance.json")
            if provenance_path.exists():
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                record["consent_id"] = provenance.get("consent_id")
                record["anna_provenance"] = provenance.get("provenance")
            return record
        record["manual_reason"] = f"OA routes failed; Anna's Archive fallback {status}."

    if record.get("doi") or record.get("url"):
        record["pdf_status"] = "manual_needed"
        if not record.get("manual_reason"):
            record["manual_reason"] = "No open-access PDF was downloadable via direct URL, PMC OA, or Unpaywall."
    elif record["pdf_status"] != "failed":
        record["pdf_status"] = "no_pdf"
    return record


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_found": len(records),
        "downloaded": sum(1 for item in records if item.get("pdf_status") == "downloaded"),
        "no_pdf": sum(1 for item in records if item.get("pdf_status") == "no_pdf"),
        "manual_needed": sum(1 for item in records if item.get("pdf_status") == "manual_needed"),
        "failed": sum(1 for item in records if item.get("pdf_status") == "failed"),
        "anna_downloaded": sum(1 for item in records if item.get("pdf_source") == ANNA_SOURCE),
    }


def rescue_status_for_record(record: dict[str, Any]) -> tuple[str, str | None]:
    status = record.get("pdf_status")
    if status == "downloaded":
        return "downloaded", None
    if status == "manual_needed":
        reason = record.get("manual_reason") or ""
        if "Anna" in reason:
            return "manual_needed", "anna_failed"
        return "manual_needed", "paywall"
    if status == "failed":
        return "failed", "network"
    return "manual_needed", "no_match"


def build_source_rescue(records: list[dict[str, Any]], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    matched_record_ids: set[int] = set()
    for target in targets:
        matches = [record for record in records if target_matches_record(target, record)]
        if matches:
            record = matches[0]
            matched_record_ids.add(id(record))
            status, failure = rescue_status_for_record(record)
            entries.append({
                "target_id": target.get("target_id"),
                "title": record.get("title") or target.get("title") or "",
                "doi": normalize_doi(record.get("doi")) or target.get("doi") or "",
                "pmid": record.get("pmid") or target.get("pmid") or "",
                "pmcid": record.get("pmcid") or target.get("pmcid") or "",
                "required": bool(target.get("required")),
                "status": status,
                "failure_reason": failure,
                "pdf_source": record.get("pdf_source"),
                "pdf_path": record.get("pdf_path"),
                "notebook_source_id": None,
                "notes": [record.get("manual_reason")] if record.get("manual_reason") else [],
            })
        else:
            entries.append({
                "target_id": target.get("target_id"),
                "title": target.get("title") or "",
                "doi": target.get("doi") or "",
                "pmid": target.get("pmid") or "",
                "pmcid": target.get("pmcid") or "",
                "required": bool(target.get("required")),
                "status": "manual_needed",
                "failure_reason": "no_match",
                "pdf_source": None,
                "pdf_path": None,
                "notebook_source_id": None,
                "notes": ["No matching candidate record was discovered."],
            })

    if not targets:
        for record in records:
            status, failure = rescue_status_for_record(record)
            entries.append({
                "target_id": next(iter(record_identifiers(record)), normalize_title(record.get("title") or "")),
                "title": record.get("title") or "",
                "doi": normalize_doi(record.get("doi")),
                "pmid": record.get("pmid") or "",
                "pmcid": record.get("pmcid") or "",
                "required": False,
                "status": status,
                "failure_reason": failure,
                "pdf_source": record.get("pdf_source"),
                "pdf_path": record.get("pdf_path"),
                "notebook_source_id": None,
                "notes": [record.get("manual_reason")] if record.get("manual_reason") else [],
            })
    return entries


def write_candidate_sources(slug: str, records: list[dict[str, Any]], output_dir: Path) -> Path:
    output_path = output_dir / "candidate-sources.json"
    output_path.write_text(json.dumps({"slug": slug, "date": date.today().isoformat(), "candidates": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def write_source_rescue(entries: list[dict[str, Any]], output_dir: Path) -> Path:
    output_path = output_dir / "source-rescue.json"
    output_path.write_text(json.dumps({"date": date.today().isoformat(), "sources": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def write_download_plan(slug: str, records: list[dict[str, Any]], targets: list[dict[str, Any]], output_dir: Path) -> Path:
    """Write a human-reviewable acquisition plan before any PDF download."""
    output_path = output_dir / "download-plan.md"
    lines = [
        f"# Download plan - {slug}",
        "",
        "This plan separates bibliographic priority from full-text availability.",
        "A paywalled paper is not treated as irrelevant; it is queued for manual rescue.",
        "",
        "## Review instructions",
        "",
        "- Confirm which high-priority papers should be rescued.",
        "- If you have institutional or author access, obtain the PDF legally.",
        "- Place rescued PDFs in the papers directory shown by the run.",
        "- Resume with the command recorded in STATUS.md.",
        "",
        "## Candidates",
        "",
    ]
    for index, record in enumerate(records, start=1):
        priority = review_priority(record, targets)
        availability = availability_status(record)
        identifiers = ", ".join(filter(None, [record.get("doi"), record.get("pmid"), record.get("pmcid")])) or "no stable identifier"
        lines.extend([
            f"### {index}. {record.get('title') or '(untitled)'}",
            f"- bibliographic_priority: `{priority}`",
            f"- availability: `{availability}`",
            f"- year: `{record.get('year') or 'unknown'}`",
            f"- identifiers: `{identifiers}`",
            f"- discovered_by: `{', '.join(record.get('sources') or [])}`",
            f"- abstract_available: `{bool(record.get('abstract'))}`",
            f"- pdf_url: `{record.get('pdf_url') or 'not found'}`",
            "",
        ])
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def suggested_manual_pdf_path(item: dict[str, Any], output_dir: Path) -> Path:
    identifier = item.get("doi") or item.get("pmid") or item.get("pmcid") or item.get("target_id") or item.get("title") or "required-source"
    title = item.get("title") or identifier
    filename = f"{slugify_fragment(str(identifier), default='source', max_words=4)}_{slugify_fragment(str(title), default='paper', max_words=8)}.pdf"
    return output_dir / filename


def write_missing_sources(entries: list[dict[str, Any]], output_dir: Path) -> Path:
    missing = [item for item in entries if item.get("required") and item.get("status") not in ("downloaded", "notebook_ready")]
    output_path = output_dir / "missing-sources.md"
    lines = ["# Missing required sources", ""]
    if not missing:
        lines.append("No required sources are missing.")
    else:
        lines.extend([
            "Manual rescue checklist:",
            "",
            "- Verify an authoritative open-access PDF URL before downloading.",
            "- Save each verified PDF to its suggested destination path below.",
            "- Re-run the normal pipeline/import step against this same papers directory.",
            "",
        ])
        for item in missing:
            lines.append(f"- `{item.get('target_id')}` - {item.get('title') or '(no title)'}")
            lines.append(f"  - status: `{item.get('status')}`")
            lines.append(f"  - failure_reason: `{item.get('failure_reason')}`")
            if item.get("doi"):
                lines.append(f"  - doi: `{item.get('doi')}`")
            if item.get("pmid"):
                lines.append(f"  - pmid: `{item.get('pmid')}`")
            if item.get("pmcid"):
                lines.append(f"  - pmcid: `{item.get('pmcid')}`")
            lines.append("  - download_url: `TBD: verify authoritative OA PDF URL`")
            lines.append(f"  - suggested_destination: `{suggested_manual_pdf_path(item, output_dir)}`")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def write_search_artifacts(slug: str, queries: list[str], records: list[dict[str, Any]], targets: list[dict[str, Any]], output_dir: Path) -> dict[str, Path]:
    payload = build_output(slug, queries, records)
    rescue_entries = build_source_rescue(records, targets)
    return {
        "output": write_output(slug, payload, output_dir),
        "candidate": write_candidate_sources(slug, records, output_dir),
        "rescue": write_source_rescue(rescue_entries, output_dir),
        "missing": write_missing_sources(rescue_entries, output_dir),
        "download_plan": write_download_plan(slug, records, targets, output_dir),
    }


def mark_records_pending_acquisition(records: list[dict[str, Any]]) -> None:
    for record in records:
        if record.get("pdf_status") is None:
            record["pdf_status"] = "manual_needed"
            record["pdf_path"] = None
            record["pdf_source"] = None
            record["manual_reason"] = "Acquisition pending; run did not complete this record yet."


def acquire_records_incrementally(
    slug: str,
    queries: list[str],
    records: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    save_dir: Path,
    min_oa: bool,
    allow_anna_fallback: bool,
) -> dict[str, Path]:
    mark_records_pending_acquisition(records)
    paths = write_search_artifacts(slug, queries, records, targets, save_dir)
    for record in records:
        try:
            download_for_record(record, save_dir, min_oa, allow_anna_fallback=allow_anna_fallback)
        except Exception as exc:
            record["pdf_status"] = "failed"
            record["pdf_path"] = None
            record["pdf_source"] = None
            record["manual_reason"] = f"Acquisition failed: {type(exc).__name__}: {exc}"
        paths = write_search_artifacts(slug, queries, records, targets, save_dir)
    return paths


def discover_prepare_records(queries: list[str], sources: list[str], max_results: int, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_results = run_searches(discovery_queries(queries, targets), sources, max_results)
    records = dedupe_records(raw_results)
    enrich_records(records)
    for record in records:
        score_record_confidence(record, targets)
    records.sort(
        key=lambda item: (
            target_priority(item, targets),
            -(item.get("identifier_confidence") or 0),
            -(item.get("title_match_confidence") or 0),
            -int(item.get("year") or 0),
            item.get("title") or "",
        )
    )
    return records


def run_topic_pipeline(
    slug: str,
    queries: list[str],
    sources: list[str],
    max_results: int,
    save_dir: Path,
    target_config: dict[str, Any],
    min_oa: bool = False,
    allow_anna_fallback: bool = False,
    scout_only: bool = False,
    resolve_only: bool = False,
    review_before_acquisition: bool = False,
) -> tuple[dict[str, Any], dict[str, Path]]:
    save_dir.mkdir(parents=True, exist_ok=True)
    allow_anna = bool(allow_anna_fallback or target_config.get("allow_anna_fallback"))
    targets = normalize_targets(target_config)
    records = discover_prepare_records(queries, sources, max_results, targets)

    if scout_only or resolve_only or review_before_acquisition:
        for record in records:
            record["pdf_status"] = "candidate"
            record["pdf_path"] = None
            record["pdf_source"] = None
            record["manual_reason"] = "Review/scout/resolve mode did not acquire PDFs."
        paths = write_search_artifacts(slug, queries, records, targets, save_dir)
    else:
        paths = acquire_records_incrementally(slug, queries, records, targets, save_dir, min_oa, allow_anna)

    payload = build_output(slug, queries, records)
    return payload, paths


def build_output(slug: str, queries: list[str], records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "slug": slug,
        "queries": queries,
        "date": date.today().isoformat(),
        "papers": [
            {
                "title": record["title"],
                "authors": record["authors"],
                "year": record["year"],
                "doi": record["doi"],
                "pmid": record["pmid"],
                "pmcid": record["pmcid"],
                "abstract": record["abstract"],
                "is_oa": bool(record["is_oa"]),
                "pdf_url": record["pdf_url"],
                "tgz_url": record["tgz_url"],
                "pdf_path": record["pdf_path"],
                "pdf_status": record["pdf_status"],
                "pdf_source": record.get("pdf_source"),
                "oa_sources": record.get("oa_sources") or [],
                "manual_reason": record.get("manual_reason"),
                "source": record["source"],
                "sources": record["sources"],
                "url": record["url"],
                "identifier_confidence": record.get("identifier_confidence", 0),
                "title_match_confidence": record.get("title_match_confidence", 0),
                "source_match_reason": record.get("source_match_reason", ""),
                "acquisition_policy": record.get("acquisition_policy", "oa_first"),
                "fallback_after": record.get("fallback_after") or [],
                "acquisition_attempts": record.get("acquisition_attempts") or [],
                "consent_id": record.get("consent_id"),
                "anna_provenance": record.get("anna_provenance"),
            }
            for record in records
        ],
        "stats": summarize(records),
    }


def write_output(slug: str, payload: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"search-{slug}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Search and download papers for a topic")
    parser.add_argument("--slug", help="Topic slug in kebab-case")
    parser.add_argument("--queries", help="JSON array of query strings")
    parser.add_argument("--query", help="Legacy single-query alias")
    parser.add_argument("--sources", default=DEFAULT_SOURCES, help="Comma-separated list of sources")
    parser.add_argument("--n", type=int, default=None, help="Max results per query per source")
    parser.add_argument("--max", dest="legacy_max", type=int, default=None, help="Legacy alias for --n")
    parser.add_argument("--save-dir", default="./papers", help="Directory for downloaded PDFs")
    parser.add_argument("--must-have-file", help="JSON object/array with must_have/nice_to_have source targets")
    parser.add_argument("--allow-anna-fallback", action="store_true", help="Try Anna's Archive after all OA routes fail")
    parser.add_argument("--scout-only", action="store_true", help="Discover and resolve candidates without downloading PDFs")
    parser.add_argument("--resolve-only", action="store_true", help="Resolve metadata and rescue queue without downloading PDFs")
    parser.add_argument("--review-before-acquisition", action="store_true", help="Write download-plan.md and stop before attempting PDF acquisition")
    parser.add_argument(
        "--min-oa",
        action="store_true",
        help="Compatibility flag; Hermes auto-downloads only OA PDFs and marks closed papers as manual_needed",
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the final JSON payload as a single stdout line for callers that need structured output",
    )
    args = parser.parse_args()

    if args.queries:
        queries = parse_queries(args.queries)
    elif args.query:
        queries = [args.query.strip()]
    else:
        raise SystemExit("ERROR: provide --queries or legacy --query")

    slug = (args.slug or "").strip() or slugify_fragment(queries[0], default="search", max_words=6)
    sources = parse_sources(args.sources)
    max_results = args.n if args.n is not None else args.legacy_max
    if max_results is None:
        max_results = 5
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    target_config = load_target_file(args.must_have_file)
    payload, paths = run_topic_pipeline(
        slug=slug,
        queries=queries,
        sources=sources,
        max_results=max_results,
        save_dir=save_dir,
        target_config=target_config,
        min_oa=args.min_oa,
        allow_anna_fallback=args.allow_anna_fallback,
        scout_only=args.scout_only,
        resolve_only=args.resolve_only,
        review_before_acquisition=args.review_before_acquisition,
    )
    records = payload["papers"]
    oa_available = sum(1 for item in records if item.get("is_oa"))

    print(f"Papers encontrados: {len(records)} (deduplicados)")
    print(f"PDFs descargados: {payload['stats']['downloaded']} / {oa_available} OA disponibles")
    print(f"Anna fallback downloads: {payload['stats'].get('anna_downloaded', 0)}")
    print(f"Guardados en: {save_dir}")
    print(f"Metadata: {paths['output']}")
    print(f"Candidate sources: {paths['candidate']}")
    print(f"Source rescue: {paths['rescue']}")
    print(f"Missing sources: {paths['missing']}")
    print(f"Download plan: {paths['download_plan']}")
    print(f"Manual needed: {payload['stats']['manual_needed']} papers identificados sin PDF OA descargable")
    print(f"Sin PDF/DOI util: {payload['stats']['no_pdf']} papers")
    if args.stdout_json:
        print(json.dumps(payload, ensure_ascii=False))
    if args.review_before_acquisition:
        print("NEEDS_SOURCE_REVIEW")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
