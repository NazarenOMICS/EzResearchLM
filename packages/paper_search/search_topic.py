"""Literature search for EZ: one query against one provider, and deterministic deduplication.

EZ calls search_single() for each planned query and merges the results with
dedupe_records() and same_identity(). Downloading and open-access resolution live in
ez.acquisition.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from paper_search_mcp.academic_platforms.crossref import CrossRefSearcher
from paper_search_mcp.academic_platforms.europepmc import EuropePMCSearcher
from paper_search_mcp.academic_platforms.openalex import OpenAlexSearcher
from paper_search_mcp.academic_platforms.pubmed import PubMedSearcher
from paper_search_mcp.academic_platforms.semantic import SemanticSearcher
from paper_search_mcp.paper import Paper

SEARCHER_FACTORIES: dict[str, Callable[[], Any]] = {
    "pubmed": PubMedSearcher,
    "europepmc": EuropePMCSearcher,
    "openalex": OpenAlexSearcher,
    "semantic": SemanticSearcher,
    "crossref": CrossRefSearcher,
}


def normalize_doi(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"^(doi:)\s*", "", text)
    return text.strip().rstrip(".")


def normalize_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


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


def identifier_value(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if key == "doi":
        return normalize_doi(value)
    if key == "pmid":
        return re.sub(r"^pmid:?\s*", "", value.lower())
    if key == "pmcid":
        value = value.upper()
        return ("PMC" + value) if value.isdigit() else value
    return value.lower()


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic and transitive: a DOI-only and a PMID-only record merge through a record with both."""
    def order(row: dict[str, Any]) -> tuple:
        return (identifier_value(row, "doi"), identifier_value(row, "pmid"), identifier_value(row, "pmcid"),
                normalize_title(str(row.get("title") or "")), str(row.get("source") or ""), json.dumps(row, sort_keys=True, default=str))
    grouped: list[dict[str, Any]] = []
    for record in sorted(records, key=order):
        record["doi"] = normalize_doi(record.get("doi"))
        match = next((i for i, previous in enumerate(grouped) if same_identity(previous, record)), None)
        if match is None:
            grouped.append(record)
        else:
            grouped[match] = merge_records(grouped[match], record)
    changed = True
    while changed:
        changed = False
        for i in range(len(grouped)):
            j = next((j for j in range(i + 1, len(grouped)) if same_identity(grouped[i], grouped[j])), None)
            if j is not None:
                grouped[i] = merge_records(grouped[i], grouped.pop(j))
                changed = True
                break
    return grouped


def same_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Exact stable identifiers, never contradictory IDs or title-only similarity."""
    ids = ("doi", "pmid", "pmcid")
    shared = [key for key in ids if identifier_value(left, key) and identifier_value(right, key)]
    if shared:
        return all(identifier_value(left, key) == identifier_value(right, key) for key in shared)
    if any(identifier_value(row, key) for row in (left, right) for key in ids):
        return False
    fields = ("title", "year", "authors")
    return all(left.get(key) and right.get(key) and normalize_title(str(left[key])) == normalize_title(str(right[key])) for key in fields)


def search_single(source: str, query: str, max_results: int) -> list[dict[str, Any]]:
    searcher = SEARCHER_FACTORIES[source]()
    papers = searcher.search(query, max_results=max_results)
    return [record_from_paper(paper, query, source) for paper in papers]

