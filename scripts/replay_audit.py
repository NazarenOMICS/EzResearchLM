#!/usr/bin/env python3
"""Read-only offline replay of EZ audit artifacts.

The tool reads JSON/Markdown/PDF files under an explicitly supplied evidence root,
computes counts and hashes in memory, and writes exactly one JSON result file chosen
with --output. It never imports EZ, contacts a provider, or changes the input tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_VERSION = "2"
BASE_AUDIT_COMMIT = "c3e66c7d8311164acaceba01b887af98f564c3d8"
_SENSITIVE = re.compile(
    r"(?:^|[._-])(?:cookies?|tokens?|storage[_-]?state|secrets?|credentials?|auth|authentication)(?:$|[._-])",
    re.I,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_files(root: Path) -> list[Path]:
    """Return files while pruning credential-bearing names at every path level."""
    found: list[Path] = []
    for base, dirs, files in os.walk(root):
        here = Path(base)
        dirs[:] = [name for name in dirs if not _SENSITIVE.search(name)]
        for name in files:
            if not _SENSITIVE.search(name):
                found.append(here / name)
    return sorted(found)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def inventory(root: Path, suffixes: set[str] | None = None) -> dict[str, Any]:
    files = safe_files(root)
    if suffixes is not None:
        normalized = {suffix.lower() for suffix in suffixes}
        files = [path for path in files if path.suffix.lower() in normalized]
    rows = []
    for path in files:
        data = path.read_bytes()
        rows.append((path, len(data), sha256_bytes(data)))
    contents = Counter(digest for _, _, digest in rows)
    return {
        "file_count": len(rows),
        "unique_content_count": len(contents),
        "logical_bytes": sum(size for _, size, _ in rows),
        "unique_content_bytes": sum(size for digest, size in _unique_sizes(rows).items()),
        "files": [
            {"relative_path": path.relative_to(root).as_posix(), "bytes": size, "sha256": digest}
            for path, size, digest in rows
        ],
        "duplicate_content_groups": sum(1 for count in contents.values() if count > 1),
    }


def _unique_sizes(rows: list[tuple[Path, int, str]]) -> dict[str, int]:
    return {digest: size for _, size, digest in rows}


def discovery_replay(root: Path) -> dict[str, Any]:
    sessions = []
    total_candidates = 0
    provider_counts: Counter[str] = Counter()
    for query_path in sorted(root.glob("runs/**/discovery/*/queries.json")):
        query = read_json(query_path)
        candidate_path = query_path.with_name("candidate-sources.json")
        candidates_obj = read_json(candidate_path) if candidate_path.exists() else None
        candidates = candidates_obj.get("candidates", []) if isinstance(candidates_obj, dict) else []
        if not isinstance(candidates, list):
            candidates = []
        provider = str(query.get("provider", "unknown")) if isinstance(query, dict) else "unknown"
        count = len(candidates)
        total_candidates += count
        provider_counts[provider] += count
        sessions.append({
            "run": query_path.parents[2].name,
            "session": query_path.parent.name,
            "provider": provider,
            "query_sha256": sha256_bytes(query_path.read_bytes()),
            "candidate_file_sha256": sha256_bytes(candidate_path.read_bytes()) if candidate_path.exists() else None,
            "candidate_count": count,
            "status": candidates_obj.get("status") if isinstance(candidates_obj, dict) else "missing",
        })
    return {
        "session_count": len(sessions),
        "candidate_record_count_raw": total_candidates,
        "candidate_records_by_provider": dict(sorted(provider_counts.items())),
        "sessions": sessions,
    }


def screening_replay(root: Path) -> dict[str, Any]:
    runs = []
    paths = list(root.glob("runs/**/screening-request.json"))
    paths += list(root.glob("runs/**/proposals/screening-*.json"))
    for path in sorted(set(paths)):
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        candidates = data.get("candidates", [])
        decisions = data.get("decisions", [])
        if not isinstance(candidates, list):
            candidates = []
        if not isinstance(decisions, list):
            decisions = []
        decisions_by_status: Counter[str] = Counter()
        for item in decisions:
            if isinstance(item, dict):
                status = item.get("decision", item.get("status", "unspecified"))
                decisions_by_status[str(status)] += 1
        is_proposal = path.parent.name == "proposals"
        candidate_ids = [str(item["source_id"]) for item in candidates if isinstance(item, dict) and item.get("source_id")]
        decision_ids = [str(item["source_id"]) for item in decisions if isinstance(item, dict) and item.get("source_id")]
        runs.append({
            "run": path.parents[1].name if is_proposal else path.parent.name,
            "artifact_kind": "screening_decision_snapshot" if is_proposal else "screening_candidate_request",
            "candidate_count": len(candidates),
            "decision_count": len(decisions),
            "candidate_source_ids": candidate_ids,
            "decision_source_ids": decision_ids,
            "decisions_by_status": dict(sorted(decisions_by_status.items())),
            "request_sha256": sha256_bytes(path.read_bytes()),
        })
    submitted = [row for row in runs if row["artifact_kind"] == "screening_candidate_request"]
    proposals = [row for row in runs if row["artifact_kind"] == "screening_decision_snapshot"]
    by_run: dict[str, dict[str, set[str]]] = {}
    for row in submitted:
        by_run.setdefault(row["run"], {"submitted": set(), "decided": set()})["submitted"].update(row["candidate_source_ids"])
    for row in proposals:
        by_run.setdefault(row["run"], {"submitted": set(), "decided": set()})["decided"].update(row["decision_source_ids"])
    reconciliation = []
    for run, sets in sorted(by_run.items()):
        reconciliation.append({
            "run": run,
            "submitted_candidate_id_count": len(sets["submitted"]),
            "decision_id_count": len(sets["decided"]),
            "decision_ids_matching_submitted_candidates": len(sets["submitted"] & sets["decided"]),
            "decision_ids_not_in_captured_requests": len(sets["decided"] - sets["submitted"]),
            "submitted_ids_without_captured_decision": len(sets["submitted"] - sets["decided"]),
        })
    return {"run_count": len(runs), "runs": runs, "request_decision_reconciliation": reconciliation}


_STOPWORDS = {
    "que", "qué", "como", "cómo", "sobre", "para", "entre", "desde", "cual", "cuál", "cuales", "cuáles",
    "what", "which", "with", "from", "this", "that", "efecto", "efectos", "se", "sabe", "conoce", "según", "segun",
}


def _topic_words(value: str) -> set[str]:
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    normalized = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", value)).encode("ascii", "ignore").decode().casefold()
    return {word for word in re.findall(r"[a-z0-9]+", normalized) if len(word) > 3 and word not in _STOPWORDS}


def _normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"^(doi:)\s*", "", text)
    return text.strip().rstrip(".")


def _identifier(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if key == "doi":
        return _normalize_doi(value)
    if key == "pmid":
        return re.sub(r"^pmid:?\s*", "", value.lower())
    if key == "pmcid":
        value = value.upper()
        return ("PMC" + value) if value.isdigit() else value
    return value


def _normalize_title(title: Any) -> str:
    text = re.sub(r"\s+", " ", str(title or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _same_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    shared = [key for key in ("doi", "pmid", "pmcid") if _identifier(left, key) and _identifier(right, key)]
    if shared:
        return all(_identifier(left, key) == _identifier(right, key) for key in shared)
    if any(_identifier(row, key) for row in (left, right) for key in ("doi", "pmid", "pmcid")):
        return False
    fields = ("title", "year", "authors")
    return all(left.get(key) and right.get(key) and _normalize_title(left[key]) == _normalize_title(right[key]) for key in fields)


def citation_expansion_replay(root: Path) -> dict[str, Any]:
    """Reproduce c3e66c7's citation candidate identity, eligibility, and top-40 ranking."""
    result = []
    for run_dir in sorted((root / "runs").glob("ez-*")):
        raw_path = run_dir / "discovery" / "citations.json"
        request_path = run_dir / "discovery" / "citations-request.json"
        state_path = run_dir / "run-state.json"
        sources_path = run_dir / "sources.json"
        contract_path = run_dir / "research-contract.json"
        if not all(path.exists() for path in (raw_path, request_path, state_path, sources_path, contract_path)):
            continue
        raw_data = read_json(raw_path)
        request = read_json(request_path)
        state = read_json(state_path)
        sources = read_json(sources_path)
        contract = read_json(contract_path)
        if not isinstance(raw_data, dict) or not isinstance(request, list) or not isinstance(state, dict) or not isinstance(sources, list) or not isinstance(contract, dict):
            continue
        raw_records = raw_data.get("records", [])
        if not isinstance(raw_records, list):
            continue
        existing = [row for row in sources if isinstance(row, dict) and row.get("discovery_origin") != "citations"]
        merged: list[dict[str, Any]] = []
        skipped_existing = 0
        duplicate_records = 0
        for original in raw_records:
            if not isinstance(original, dict):
                continue
            record = dict(original)
            record["doi"] = _normalize_doi(record.get("doi"))
            if any(_same_identity(row, record) for row in existing):
                skipped_existing += 1
                continue
            match = next((row for row in merged if _same_identity(row, record)), None)
            if match is None:
                merged.append(record)
                continue
            duplicate_records += 1
            match.setdefault("links", []).extend(record.get("links", []))
            for key, value in record.items():
                if value and not match.get(key):
                    match[key] = value
        question = contract.get("question", {})
        question_text = question.get("original", "") if isinstance(question, dict) else str(question or "")
        plan = contract.get("plan", {})
        phrases = [question_text]
        if isinstance(plan, dict):
            for group in ("queries", "notebook_questions"):
                for item in plan.get(group, []) if isinstance(plan.get(group, []), list) else []:
                    if isinstance(item, dict):
                        phrases.append(str(item.get("text", "")))
        words = _topic_words(" ".join(phrases))
        ranked: list[tuple[int, int, str, dict[str, Any]]] = []
        eligible_count = 0
        for index, record in enumerate(merged):
            links = record.get("links", []) if isinstance(record.get("links", []), list) else []
            linked = len({item.get("seed") for item in links if isinstance(item, dict) and item.get("seed")})
            overlap = len(words & _topic_words(str(record.get("title", "")) + " " + str(record.get("abstract") or "")))
            if linked >= 2 or overlap >= 2:
                eligible_count += 1
                ranked.append((linked * 2 + overlap, index, str(record.get("doi") or record.get("pmid") or record.get("title") or "").lower(), record))
        ranked.sort(key=lambda item: -item[0])
        chosen = ranked[:40]
        actual_added = [row for row in sources if isinstance(row, dict) and row.get("discovery_origin") == "citations"]
        expected_ids = ["src-" + hashlib.sha256(item[2].encode()).hexdigest()[:20] for item in chosen]
        actual_ids = [str(row.get("source_id", "")) for row in actual_added]
        screening_path = run_dir / "screening-request.json"
        screening_request = read_json(screening_path) if screening_path.exists() else None
        screening_candidates = screening_request.get("candidates", []) if isinstance(screening_request, dict) else []
        screening_ids = [str(row["source_id"]) for row in screening_candidates if isinstance(row, dict) and row.get("source_id")]
        state_expansion = state.get("citation_expansion", {})
        result.append({
            "run": run_dir.name,
            "base_filter_source": "packages/ez/engine.py@" + BASE_AUDIT_COMMIT,
            "raw_record_count": len(raw_records),
            "seed_count_in_capture": len(request),
            "raw_file_sha256": sha256_bytes(raw_path.read_bytes()),
            "request_file_sha256": sha256_bytes(request_path.read_bytes()),
            "existing_source_identity_exclusions": skipped_existing,
            "duplicate_identity_records_merged": duplicate_records,
            "post_identity_merge_found": len(merged),
            "eligible_by_link_or_topic_rule": eligible_count,
            "eligible_rule": "unique linked seeds >= 2 OR title+abstract topic-word overlap >= 2",
            "rank_formula": "2 * unique linked seeds + topic-word overlap; descending; stable ties; first 40",
            "replayed_top40_count": len(chosen),
            "actual_citation_sources_count": len(actual_added),
            "top40_source_id_set_matches_saved_sources": set(expected_ids) == set(actual_ids),
            "top40_order_matches_saved_sources": expected_ids == actual_ids,
            "top40_set_difference_count": len(set(expected_ids) ^ set(actual_ids)),
            "screening_request_candidate_count": len(screening_ids),
            "top40_source_id_set_matches_screening_request": set(expected_ids) == set(screening_ids),
            "screening_request_file_sha256": sha256_bytes(screening_path.read_bytes()) if screening_path.exists() else None,
            "state_found": state_expansion.get("found") if isinstance(state_expansion, dict) else None,
            "state_added": state_expansion.get("added") if isinstance(state_expansion, dict) else None,
            "state_seed_count": state_expansion.get("seeds") if isinstance(state_expansion, dict) else None,
        })
    return {"run_count": len(result), "runs": result}


def _ascii_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def _surname(author: str) -> str:
    author = author.strip()
    if "," in author:
        return author.split(",", 1)[0].strip()
    pieces = author.split()
    return pieces[-1] if pieces else ""


def _author_surnames(value: Any) -> tuple[str, str] | None:
    if isinstance(value, list):
        authors = [str(item.get("name", item.get("family", ""))) if isinstance(item, dict) else str(item) for item in value]
    elif isinstance(value, str):
        authors = re.split(r"\s+and\s+|;\s*", value)
    else:
        return None
    authors = [author.strip() for author in authors if author and author.strip()]
    if not authors:
        return None
    return _ascii_key(_surname(authors[0])), _ascii_key(_surname(authors[-1]))


def last_author_notes_replay(root: Path) -> dict[str, Any]:
    """Match each source-note filename key against source metadata by DOI, after ASCII transliteration."""
    author_metadata: dict[str, set[tuple[str, str]]] = {}
    for path in sorted((root / "runs").glob("ez-*/sources.json")):
        records = read_json(path)
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict) or not record.get("doi"):
                continue
            surnames = _author_surnames(record.get("authors"))
            if surnames:
                author_metadata.setdefault(_normalize_doi(record["doi"]), set()).add(surnames)
    notes = sorted(path for path in safe_files(root) if "notes" in path.parts and "sources" in path.parts and path.suffix.lower() == ".md")
    matched = 0
    any_last_match = 0
    all_last_match = 0
    any_first_match = 0
    metadata_variant_count = 0
    note_hashes = []
    ambiguous_notes = 0
    for path in notes:
        body = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"(?im)^doi:\s*(.+?)\s*$", body)
        doi = _normalize_doi(match.group(1)) if match else ""
        variants = author_metadata.get(doi, set())
        prefix = re.match(r"([A-Za-z]+)\d{4}", path.name)
        note_key = _ascii_key(prefix.group(1)) if prefix else ""
        note_hashes.append(sha256_bytes(path.read_bytes()))
        metadata_variant_count += len(variants)
        if len(variants) > 1:
            ambiguous_notes += 1
        if not variants:
            continue
        matched += 1
        last_matches = [note_key == last for _, last in variants]
        first_matches = [note_key == first for first, _ in variants]
        any_last_match += any(last_matches)
        all_last_match += all(last_matches)
        any_first_match += any(first_matches)
    return {
        "source_note_count": len(notes),
        "notes_with_doi_matched_source_metadata": matched,
        "metadata_author_variants_total": metadata_variant_count,
        "notes_with_conflicting_author_metadata_variants": ambiguous_notes,
        "filename_keys_matching_last_author_any_recorded_variant": any_last_match,
        "filename_keys_matching_last_author_all_recorded_variants": all_last_match,
        "filename_keys_matching_first_author_any_recorded_variant": any_first_match,
        "normalization": "NFKD ASCII transliteration, casefold, remove non-alphanumeric characters",
        "filename_key_rule": "leading alphabetic token immediately before a four-digit year",
        "source_note_sha256": note_hashes,
    }


def qa_replay(root: Path) -> dict[str, Any]:
    qa_files = sorted(root.glob("runs/**/qa/*.json"))
    qa_files = [p for p in qa_files if p.name != "manifest.json" and not _SENSITIVE.search(str(p))]
    statuses: Counter[str] = Counter()
    valid_count = 0
    for path in qa_files:
        data = read_json(path)
        if not isinstance(data, dict) or not isinstance(data.get("answer"), str) or not data["answer"].strip():
            continue
        valid_count += 1
        # Only count explicit machine-labelled status fields; do not infer answer quality.
        for key in ("status", "sufficiency", "classification"):
            if key in data:
                statuses[str(data[key]).lower()] += 1
    return {
        "qa_file_count": len(qa_files),
        "nonempty_answer_count": valid_count,
        "follow_up_count": _count_qa_followups(qa_files),
        "explicit_machine_status_counts": dict(sorted(statuses.items())),
        "scientific_completeness_assessed": False,
    }


def _count_qa_followups(paths: list[Path]) -> int:
    count = 0
    for path in paths:
        data = read_json(path)
        if isinstance(data, dict) and data.get("is_follow_up") is True:
            count += 1
    return count


def contract_replay(root: Path) -> dict[str, Any]:
    contracts = sorted((root / "runs").glob("ez-*/research-contract.json"))
    question_count = 0
    parent_count = 0
    search_query_count = 0
    notebook_question_count = 0
    reuse_question_count = 0
    for path in contracts:
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        question = data.get("question", {})
        question_count += bool(question.get("original") if isinstance(question, dict) else question)
        parent_count += bool(data.get("parent_contract_hash"))
        plan = data.get("plan", {})
        if isinstance(plan, dict):
            reuse_question_count += bool(plan.get("discovery_mode") == "reuse_only" and
                                         (question.get("original") if isinstance(question, dict) else question))
            search_query_count += len(plan.get("queries", [])) if isinstance(plan.get("queries", []), list) else 0
            notebook_question_count += len(plan.get("notebook_questions", [])) if isinstance(plan.get("notebook_questions", []), list) else 0
    recall_artifacts = []
    for path in safe_files(root):
        if "recall" in path.name.lower():
            recall_artifacts.append(path)
            continue
        if path.suffix.lower() == ".json":
            data = read_json(path)
            if isinstance(data, dict) and str(data.get("kind", data.get("type", ""))).lower() == "recall":
                recall_artifacts.append(path)
    return {
        "research_contract_count": len(contracts),
        "contracts_with_nonempty_question": question_count,
        "contracts_with_parent_contract_hash": parent_count,
        "saved_search_query_count": search_query_count,
        "saved_notebook_question_count": notebook_question_count,
        "reuse_only_contracts_with_question": reuse_question_count,
        "qa_replay": qa_replay(root),
        "recall_output_artifact_count": len(recall_artifacts),
        "recall_artifact_hashes": [sha256_bytes(path.read_bytes()) for path in recall_artifacts],
        "validity_and_sufficiency_manifest_found": False,
    }


def answer_replay(root: Path) -> dict[str, Any]:
    runs = []
    sums: Counter[str] = Counter()
    for path in sorted(root.glob("runs/**/answer.json")):
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        claims = data.get("claims", [])
        sums["answer_files"] += 1
        sums["claims"] += len(claims) if isinstance(claims, list) else 0
        delivery = data.get("delivery", "unknown")
        if delivery == "direct":
            sums["direct_answer_files"] += 1
            sums["direct_claims"] += len(claims) if isinstance(claims, list) else 0
        refs_count = 0
        latex_claims = 0
        latex_delimited_claims = 0
        for claim in claims if isinstance(claims, list) else []:
            if not isinstance(claim, dict):
                continue
            refs = claim.get("references", [])
            if isinstance(refs, list):
                refs_count += len(refs)
            text = claim.get("text", "")
            if isinstance(text, str):
                if re.search(r"\\[A-Za-z]+|\$[^$]+\$", text):
                    latex_claims += 1
                if re.search(r"\\{1,2}\((.+?)\\{1,2}\)", text):
                    latex_delimited_claims += 1
        sums["reference_records"] += refs_count
        if delivery == "direct":
            sums["direct_reference_records"] += refs_count
            sums["direct_latex_claims_detected"] += latex_claims
            sums["direct_latex_delimited_claims"] += latex_delimited_claims
        runs.append({
            "run": path.parent.name,
            "delivery": delivery,
            "claim_count": len(claims) if isinstance(claims, list) else 0,
            "answer_sha256": sha256_bytes(path.read_bytes()),
        })
    return {
        "answer_file_count": sums["answer_files"],
        "claim_count_all_saved_answers": sums["claims"],
        "direct_answer_file_count": sums["direct_answer_files"],
        "direct_claim_count": sums["direct_claims"],
        "reference_record_count_all_saved_answers": sums["reference_records"],
        "direct_reference_record_count": sums["direct_reference_records"],
        "direct_claims_with_latex_pattern_detected": sums["direct_latex_claims_detected"],
        "direct_claims_with_base_audit_latex_delimiters": sums["direct_latex_delimited_claims"],
        "direct_unique_reference_keys_source_citation_number": _unique_direct_reference_keys(root, "source_citation"),
        "direct_unique_reference_keys_source_character_range": _unique_direct_reference_keys(root, "source_range"),
        "direct_unique_cited_text_count": _unique_direct_reference_keys(root, "cited_text"),
        "runs": runs,
    }


def _unique_direct_reference_keys(root: Path, key_kind: str) -> int:
    keys = set()
    for path in sorted((root / "runs").glob("ez-*/answer.json")):
        answer = read_json(path)
        if not isinstance(answer, dict) or answer.get("delivery") != "direct":
            continue
        for claim in answer.get("claims", []) if isinstance(answer.get("claims", []), list) else []:
            if not isinstance(claim, dict):
                continue
            for ref in claim.get("references", []) if isinstance(claim.get("references", []), list) else []:
                if not isinstance(ref, dict):
                    continue
                if key_kind == "source_citation":
                    keys.add((ref.get("source_id"), ref.get("citation_number")))
                elif key_kind == "source_range":
                    keys.add((ref.get("source_id"), ref.get("start_char"), ref.get("end_char")))
                else:
                    keys.add(str(ref.get("cited_text", "")))
    return len(keys)


def qa_byte_pairs(root: Path) -> dict[str, Any]:
    """Inventory paired deliverable files; content equivalence is deliberately not guessed."""
    pairs = []
    for base in sorted((root / "runs").glob("ez-*")):
        if not base.is_dir():
            continue
        answer = base / "answer.json"
        report = base / "report.md"
        if answer.exists() and report.exists():
            pairs.append({
                "run": base.name,
                "answer_json_bytes": answer.stat().st_size,
                "report_md_bytes": report.stat().st_size,
                "answer_sha256": sha256_bytes(answer.read_bytes()),
                "report_sha256": sha256_bytes(report.read_bytes()),
                "content_equivalence": "not_asserted",
            })
    return {"paired_run_count": len(pairs), "pairs": pairs}


def equivalent_utf8_sizes(value: Any) -> dict[str, Any]:
    """Lossless JSON whitespace comparison, never a claim about EZ's lossy compact view."""
    pretty = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    compact = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert json.loads(pretty) == json.loads(compact) == value
    return {"pretty_utf8_bytes": len(pretty), "compact_utf8_bytes": len(compact),
            "saved_utf8_bytes": len(pretty) - len(compact), "parsed_content_equal": True,
            "pretty_sha256": sha256_bytes(pretty), "compact_sha256": sha256_bytes(compact)}


def lossless_bytes_replay(root: Path) -> dict[str, Any]:
    answers = [read_json(path) for path in sorted((root / "runs").glob("ez-*/answer.json"))]
    sources = [read_json(path) for path in sorted((root / "runs").glob("ez-*/sources.json"))]
    caches = []
    for path in safe_files(root):
        if "cache" in path.parts and "pages" in path.parts and path.suffix == ".json":
            value = read_json(path)
            if isinstance(value, dict) and isinstance(value.get("pages"), list):
                caches.append(value)
    value = {"saved_answers": answers, "source_metadata": sources, "cached_pdf_pages": caches}
    return {**equivalent_utf8_sizes(value), "saved_answer_count": len(answers),
            "source_manifest_count": len(sources), "pdf_page_cache_count": len(caches),
            "pdf_page_count": sum(len(cache["pages"]) for cache in caches),
            "comparison": "Identical parsed object, UTF-8 JSON indent=2 versus separators=(',', ':'); no final newline",
            "limitation": "Serialization whitespace only; not CLI compact/full savings, tokens or scientific equivalence. Cached pages are historical captures, not re-extracted or verified against PDFs here."}


def git_fingerprint(repo: Path) -> dict[str, Any]:
    def git(*args: str) -> bytes | None:
        try:
            return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    diff = git("diff", "--binary", "HEAD")
    staged = git("diff", "--cached", "--binary")
    head = git("rev-parse", "HEAD")
    base_files = {}
    for name in (
        "packages/ez/engine.py",
        "packages/ez/acquisition.py",
        "packages/ez/workspace.py",
        "packages/paper_search/search_topic.py",
        "packages/ez/audit.py",
    ):
        try:
            source = subprocess.run(
                ["git", "show", f"{BASE_AUDIT_COMMIT}:{name}"],
                cwd=repo,
                check=True,
                capture_output=True,
            ).stdout
            base_files[name] = sha256_bytes(source)
        except (OSError, subprocess.CalledProcessError):
            base_files[name] = None
    return {
        "head": head.decode("ascii", errors="replace") if head else None,
        "working_tree_diff_sha256": sha256_bytes(diff or b""),
        "staged_diff_sha256": sha256_bytes(staged or b""),
        "replay_script_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "audit_base_commit": BASE_AUDIT_COMMIT,
        "audit_base_source_sha256": base_files,
    }


def replay(root: Path, repo: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return {
        "schema_version": 1,
        "replay_script_version": SCRIPT_VERSION,
        "scope": {
            "mode": "offline_read_only",
            "input_root": str(root),
            "credential_name_filter": "cookie|token|storage_state|secret|credential|auth",
            "outputs_may_contain_source_text": False,
            "units": {"bytes": "logical file bytes", "unique_content_bytes": "one size per SHA-256 content digest"},
            "note": "Filesystem allocated space is not measured; MB and MiB must be derived explicitly as bytes/1e6 and bytes/1048576.",
        },
        "code_version": git_fingerprint(repo),
        "inventory": inventory(root / "runs") if (root / "runs").is_dir() else inventory(root),
        "D1_discovery": discovery_replay(root),
        "D2_screening": screening_replay(root),
        "D2_citation_expansion": citation_expansion_replay(root),
        "D3_queries": contract_replay(root),
        "D4_deliveries": answer_replay(root),
        "D5_bytes": qa_byte_pairs(root),
        "D5_equivalent_utf8": lossless_bytes_replay(root),
        "D6_runs_storage": inventory(root / "runs", {".pdf"}) if (root / "runs").is_dir() else inventory(root, {".pdf"}),
        "D7_last_author_notes": last_author_notes_replay(root),
        "limitations": [
            "Provider response captures absent from the evidence root cannot be reconstructed offline.",
            "Candidate records, QA counts, and file metadata do not establish scientific relevance or answer completeness.",
            "D5 equivalent UTF-8 comparison preserves all fields and measures only JSON whitespace; answer/report sizes are not comparable content.",
            "D7 uses DOI-matched recorded author strings and an explicit syntactic surname heuristic, not independently validated personal names.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Read-only historical evidence root")
    parser.add_argument("--output", required=True, type=Path, help="Single JSON destination outside the evidence root")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="Repository for version fingerprint")
    args = parser.parse_args(argv)
    root = args.root.resolve(strict=True)
    output = args.output.resolve()
    if output == root or root in output.parents:
        parser.error("--output must be outside the read-only evidence root")
    result = replay(root, args.repo.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "input_root": str(root), "status": "complete"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
