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

    target_config = search_topic.load_target_file(args.must_have_file)
    payload, paths = search_topic.run_topic_pipeline(
        slug=args.slug,
        queries=[q.strip() for q in queries],
        sources=sources,
        max_results=args.n,
        save_dir=save_dir,
        target_config=target_config,
        min_oa=args.min_oa,
        allow_anna_fallback=args.allow_anna_fallback,
        scout_only=args.scout_only,
        resolve_only=args.resolve_only,
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
    print(f"Manual needed: {payload['stats']['manual_needed']} papers identificados sin PDF OA descargable")
    print(f"Sin PDF/DOI util: {payload['stats']['no_pdf']} papers")
    if args.stdout_json:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
