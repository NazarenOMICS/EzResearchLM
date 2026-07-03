#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import search_topic


def main() -> None:
    parser = argparse.ArgumentParser(description="Stable wrapper for search_topic.py using a queries JSON file")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--queries-file", required=True, help="Path to JSON array of query strings")
    parser.add_argument("--sources", default=search_topic.DEFAULT_SOURCES)
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--save-dir", required=True)
    parser.add_argument("--min-oa", action="store_true")
    parser.add_argument("--stdout-json", action="store_true")
    parser.add_argument("--must-have-file")
    parser.add_argument("--allow-anna-fallback", action="store_true")
    parser.add_argument("--scout-only", action="store_true")
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()

    queries_path = Path(args.queries_file)
    queries = json.loads(queries_path.read_text(encoding="utf-8-sig"))
    if not isinstance(queries, list) or not queries or any(not isinstance(item, str) or not item.strip() for item in queries):
        raise SystemExit("ERROR: --queries-file must contain a non-empty JSON array of strings")

    sources = search_topic.parse_sources(args.sources)
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    raw_results = search_topic.run_searches([q.strip() for q in queries], sources, args.n)
    records = search_topic.dedupe_records(raw_results)
    search_topic.enrich_records(records)
    records.sort(key=lambda item: ((item.get("year") or 0), item.get("title") or ""), reverse=True)

    target_config = search_topic.load_target_file(args.must_have_file)
    allow_anna = bool(args.allow_anna_fallback or target_config.get("allow_anna_fallback"))
    targets = search_topic.normalize_targets(target_config)
    for record in records:
        search_topic.score_record_confidence(record, targets)

    if args.scout_only or args.resolve_only:
        for record in records:
            record["pdf_status"] = "candidate"
            record["pdf_path"] = None
            record["pdf_source"] = None
            record["manual_reason"] = "Scout/resolve mode did not acquire PDFs."
    else:
        for record in records:
            search_topic.download_for_record(record, save_dir, args.min_oa, allow_anna_fallback=allow_anna)

    payload = search_topic.build_output(args.slug, queries, records)
    output_path = search_topic.write_output(args.slug, payload, save_dir)
    candidate_path = search_topic.write_candidate_sources(args.slug, records, save_dir)
    rescue_entries = search_topic.build_source_rescue(records, targets)
    rescue_path = search_topic.write_source_rescue(rescue_entries, save_dir)
    missing_path = search_topic.write_missing_sources(rescue_entries, save_dir)
    oa_available = sum(1 for item in records if item.get("is_oa"))

    print(f"Papers encontrados: {len(records)} (deduplicados)")
    print(f"PDFs descargados: {payload['stats']['downloaded']} / {oa_available} OA disponibles")
    print(f"Anna fallback downloads: {payload['stats'].get('anna_downloaded', 0)}")
    print(f"Guardados en: {save_dir}")
    print(f"Metadata: {output_path}")
    print(f"Candidate sources: {candidate_path}")
    print(f"Source rescue: {rescue_path}")
    print(f"Missing sources: {missing_path}")
    print(f"Manual needed: {payload['stats']['manual_needed']} papers identificados sin PDF OA descargable")
    print(f"Sin PDF/DOI util: {payload['stats']['no_pdf']} papers")
    if args.stdout_json:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
