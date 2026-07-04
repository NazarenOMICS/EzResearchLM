#!/usr/bin/env python3
"""Resolve [N] citations in NotebookLM answers to [[wikilinks]].

Usage:
  # Preview resolved text to stdout
  python3 resolve_citations.py --qa /tmp/qa.json --sources /tmp/sources.json --slug my-notebook

  # Write as vault reference note
  python3 resolve_citations.py --qa /tmp/qa.json --sources /tmp/sources.json \
    --slug my-notebook --title "My Q&A" --dashboard "Dashboard Title" \
    --output "Notes/NotebookLM/my-notebook/QA/2026-02-23 My Q&A.md"

Citation resolution strategy:
  NotebookLM's references[] array contains chunks with citation_number fields.
  Each unique chunk maps to a source_id. The answer's [N] markers correspond to
  the Nth unique chunk (deduplicated by cited_text), NOT to citation_number directly.

  Steps:
  1. Deduplicate references by cited_text to get ordered unique chunks
  2. Map answer [N] -> Nth unique chunk -> source_id -> source file title
  3. [1, 2] and [3-5] expanded to individual numbers
  4. Consecutive same-source refs deduped in output
  5. Links go to [[Source Title#Passage N]] when passage mapping is provided
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VAULT = Path.cwd()  # Expected to run from vault root

BAD_TITLE_PATTERNS = [
    r"^attention required!\s*\|\s*cloudflare$",
    r"^validate user$",
    r"^https?://.+$",
]


def safe_source_title(title: str) -> str:
    safe = re.sub(r'[/:*?"<>|]', '-', title)
    safe = re.sub(r'\s+', ' ', safe).strip()
    if len(safe) > 120:
        safe = safe[:120].rstrip(' -')
    return safe


def should_skip_source(source: dict) -> bool:
    title = (source.get("title") or "").strip()
    status = (source.get("status") or "").strip().lower()
    if status and status != "ready":
        return True
    if title == "- YouTube" or len(title) < 3:
        return True
    for pattern in BAD_TITLE_PATTERNS:
        if re.match(pattern, title, re.IGNORECASE):
            return True
    return False


def build_source_map(sources_file: str, slug: str) -> dict[str, str]:
    """Build source_id -> safe filename mapping."""
    with open(sources_file, encoding="utf-8-sig") as f:
        data = json.load(f)

    mapping = {}
    for s in data["sources"]:
        if should_skip_source(s):
            continue
        mapping[s["id"]] = safe_source_title(s["title"].strip())
    return mapping


def build_pdf_map(source_map: dict[str, str], slug: str) -> dict[str, str]:
    pdf_map: dict[str, str] = {}
    sources_dir = VAULT / 'Notes' / 'NotebookLM' / slug / 'Sources'
    for title in source_map.values():
        note_path = sources_dir / f'{title}.md'
        if not note_path.exists():
            continue
        text = note_path.read_text(encoding='utf-8')
        m = re.search(r'^pdf:\s*"([^"]+)"', text, re.MULTILINE)
        if m:
            pdf_map[title] = m.group(1)
    return pdf_map


def expand_citation_spec(spec_text: str) -> list[int]:
    """Expand '1, 2, 5-8' into [1, 2, 5, 6, 7, 8]."""
    numbers = []
    for part in spec_text.split(','):
        part = part.strip()
        if '-' in part:
            try:
                a, b = part.split('-', 1)
                numbers.extend(range(int(a.strip()), int(b.strip()) + 1))
            except ValueError:
                continue
        else:
            try:
                numbers.append(int(part))
            except ValueError:
                continue
    return numbers


def build_chunk_map(references: list[dict]) -> dict[int, dict]:
    """Build answer [N] -> unique chunk mapping.

    NotebookLM's references[] repeats the same chunks many times with different
    citation_numbers. The answer's [N] markers refer to the Nth unique chunk
    (1-based, in order of first appearance), NOT to citation_number.
    """
    seen_texts = {}
    chunks = {}  # 1-based index -> ref
    for ref in references:
        key = (ref.get("cited_text") or "")[:100]
        if key and key not in seen_texts:
            idx = len(seen_texts) + 1
            seen_texts[key] = idx
            chunks[idx] = ref
    return chunks


def collect_cited_chunks(answer: str, references: list[dict]) -> list[tuple[int, dict]]:
    """Return unique cited chunks in order of first appearance in the answer."""
    chunk_map = build_chunk_map(references)
    seen: set[int] = set()
    ordered: list[tuple[int, dict]] = []

    for match in re.finditer(r'\[(\d+(?:\s*[-,]\s*\d+)*)\]', answer):
        numbers = expand_citation_spec(match.group(1))
        for n in numbers:
            if n in seen:
                continue
            ref = chunk_map.get(n)
            if not ref:
                continue
            seen.add(n)
            ordered.append((n, ref))
    return ordered


def is_good_verbatim(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    lowered = cleaned.lower()
    if len(cleaned) < 80:
        return False
    if re.fullmatch(r"[\d\W_]+", cleaned):
        return False
    if lowered.startswith("*these authors contributed equally"):
        return False
    if lowered.startswith("retrieved from"):
        return False
    if 'wikipedia.org/w/index.php' in lowered:
        return False
    if 'checking your browser' in lowered or 'recaptcha' in lowered:
        return False
    if re.fullmatch(r"[A-Za-z0-9 .,:;\-()]+", cleaned) and cleaned.count('.') <= 1 and len(cleaned.split()) < 12:
        return False
    alpha_words = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}", cleaned)
    if len(alpha_words) < 8:
        return False
    return True


def build_verbatim_section(
    answer: str,
    references: list[dict],
    source_map: dict[str, str],
    slug: str,
    passage_map: dict[str, dict[str, int]] | None = None,
    pdf_map: dict[str, str] | None = None,
) -> str:
    cited_chunks = collect_cited_chunks(answer, references)
    if not cited_chunks:
        return ""

    sources_path = f"Notes/NotebookLM/{slug}/Sources"
    blocks: list[str] = ["## Extractos citados verbatim", ""]
    kept = 0

    for _raw_idx, (_citation_idx, ref) in enumerate(cited_chunks, 1):
        sid = ref.get("source_id")
        title = source_map.get(sid)
        if not title:
            continue

        chunk_key = (ref.get("cited_text") or "")[:100]
        passage_num = None
        if passage_map:
            passage_num = (passage_map.get(sid) or {}).get(chunk_key)

        anchor = f"#Passage {passage_num}" if passage_num else ""
        note_link = f"[[{sources_path}/{title}{anchor}|Pasaje {passage_num}]]" if passage_num else f"[[{sources_path}/{title}|Nota fuente]]"
        pdf_link = f"[[{pdf_map[title]}|PDF]]" if pdf_map and title in pdf_map else ''
        quote = (ref.get("cited_text") or "").strip()
        quote = re.sub(r"\s+", " ", quote)
        if not is_good_verbatim(quote):
            continue

        kept += 1
        source_line = f"- Fuente: {note_link}" if not pdf_link else f"- Fuente: {note_link} | {pdf_link}"
        blocks.extend([
            f"### Extracto {kept}",
            source_line,
            "- Texto literal:",
            f"> {quote}",
            "",
        ])

    if kept == 0:
        return "## Extractos citados verbatim\n\n_No se conservaron extractos verbatim de calidad suficiente en esta respuesta; revisar la nota QA completa y los Source#Passage para auditar la trazabilidad._"
    return "\n".join(blocks).rstrip()


def resolve_answer(answer: str, references: list[dict], source_map: dict[str, str], slug: str,
                    passage_map: dict[str, dict[str, int]] | None = None,
                    pdf_map: dict[str, str] | None = None) -> tuple[str, list[str], dict]:
    """Replace [N] markers with [[wikilinks]]. Returns (resolved_text, all_source_titles, stats).

    Maps answer [N] to the Nth unique chunk, then to its source.
    When passage_map is provided, links include #Passage N anchors.
    """
    chunk_map = build_chunk_map(references)

    sources_path = f"Notes/NotebookLM/{slug}/Sources"

    # Stats for diagnostics
    cited_sources = set()
    total_sources = set(source_map.values())
    passage_hits = 0
    passage_misses = 0
    citation_labels: dict[tuple, int] = {}
    next_label = 1

    def make_wikilink(title: str, ref: dict | None = None) -> str:
        nonlocal passage_hits, passage_misses, next_label
        sid = ref["source_id"] if ref else title
        chunk_key = ref.get("cited_text", "")[:100] if ref else ''
        passage_num = None
        if passage_map and ref:
            source_passages = passage_map.get(sid, {})
            passage_num = source_passages.get(chunk_key)
            if passage_num:
                passage_hits += 1
            else:
                passage_misses += 1
        dedup_key = (sid, passage_num) if passage_num else (sid,)
        if dedup_key not in citation_labels:
            citation_labels[dedup_key] = next_label
            next_label += 1
        label = citation_labels[dedup_key]
        anchor = f"#Passage {passage_num}" if passage_num else ""
        return f"[[{sources_path}/{title}{anchor}|[{label}]]]"

    def replace_citation(match):
        spec = match.group(1)
        numbers = expand_citation_spec(spec)

        seen = set()
        links = []
        for n in numbers:
            ref = chunk_map.get(n)
            if not ref:
                continue
            sid = ref["source_id"]
            title = source_map.get(sid)
            if not title:
                continue
            # With passage links, dedup by (source, passage) so different
            # passages from the same source each get their own link.
            # Without passages, dedup by source only.
            chunk_key = ref.get("cited_text", "")[:100]
            passage_num = None
            if passage_map:
                source_passages = passage_map.get(sid, {})
                passage_num = source_passages.get(chunk_key)
            dedup_key = (sid, passage_num) if passage_num else (sid,)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            cited_sources.add(title)
            links.append(make_wikilink(title, ref))

        if not links:
            return match.group(0)

        return f" {' '.join(links)}"

    resolved = re.sub(
        r'\[(\d+(?:\s*[-,]\s*\d+)*)\]',
        replace_citation,
        answer
    )

    # Collect all unique sources from refs (not just cited in answer)
    all_ref_sources = set()
    for ref in references:
        sid = ref["source_id"]
        if sid in source_map:
            all_ref_sources.add(source_map[sid])

    stats = {
        "unique_chunks": len(chunk_map),
        "total_refs": len(references),
        "cited_sources": len(cited_sources),
        "total_sources": len(total_sources),
        "uncited_sources": sorted(total_sources - cited_sources),
        "passage_hits": passage_hits,
        "passage_misses": passage_misses,
    }

    return resolved, sorted(cited_sources), stats


def main():
    parser = argparse.ArgumentParser(description="Resolve NotebookLM citations to wikilinks")
    parser.add_argument("--qa", required=True, help="Path to notebooklm ask --json output")
    parser.add_argument("--sources", required=True, help="Path to notebooklm source list --json output")
    parser.add_argument("--slug", required=True, help="Notebook slug")
    parser.add_argument("--title", help="Q&A note title (required for --output)")
    parser.add_argument("--dashboard", help="Dashboard title for related links (required for --output)")
    parser.add_argument("--output", help="Vault-relative output path for reference note")
    parser.add_argument("--passages", help="Passage mapping JSON from extract_passages.py (enables #Passage N anchors)")
    parser.add_argument("--date", help="Date for frontmatter (default: today)")
    parser.add_argument("--verbose-warnings", action="store_true", help="Print full list of uncited sources")
    args = parser.parse_args()

    source_map = build_source_map(args.sources, args.slug)
    pdf_map = build_pdf_map(source_map, args.slug)
    print(f"Source map: {len(source_map)} entries", file=sys.stderr)

    passage_map = None
    if args.passages:
        with open(args.passages, encoding="utf-8") as f:
            passage_map = json.load(f)
        print(f"Passage map: {len(passage_map)} sources", file=sys.stderr)

    with open(args.qa, encoding="utf-8") as f:
        qa_data = json.load(f)

    resolved, cited_sources, stats = resolve_answer(
        qa_data["answer"], qa_data["references"], source_map, args.slug, passage_map, pdf_map
    )
    verbatim_section = build_verbatim_section(
        qa_data["answer"], qa_data["references"], source_map, args.slug, passage_map, pdf_map
    )

    # Diagnostics
    print(f"Refs: {stats['total_refs']} raw -> {stats['unique_chunks']} unique chunks", file=sys.stderr)
    print(f"Sources cited: {stats['cited_sources']}/{stats['total_sources']}", file=sys.stderr)
    if passage_map:
        print(f"Passage anchors: {stats['passage_hits']} linked, {stats['passage_misses']} source-only", file=sys.stderr)
    if stats["uncited_sources"]:
        n = len(stats["uncited_sources"])
        print(f"WARNING: {n}/{stats['total_sources']} sources uncited. Pass --verbose-warnings to list them.", file=sys.stderr)
        if getattr(args, "verbose_warnings", False):
            for s in stats["uncited_sources"]:
                print(f"  - {s}", file=sys.stderr)

    if not args.output:
        # Preview mode - print to stdout
        print(resolved)
        return

    # Write reference note
    if not args.title or not args.dashboard:
        print("ERROR: --title and --dashboard required when using --output", file=sys.stderr)
        sys.exit(1)

    from datetime import date
    note_date = args.date or date.today().isoformat()
    dashboard_path = f"Notes/Dashboards/{args.dashboard}"
    sources_path = f"Notes/NotebookLM/{args.slug}/Sources"

    cited_links = "\n".join(
        f"- [[{sources_path}/{s}|{s}]]"
        for s in cited_sources
    ) or "- Sin fuentes citadas"

    # Build uncited sources section if any exist
    uncited_section = ""
    if stats["uncited_sources"]:
        uncited_links = "\n".join(
            f"- [[{sources_path}/{s}|{s}]]"
            for s in stats["uncited_sources"]
        )
        uncited_section = f"""

## Uncited Sources

These sources were in the notebook but NotebookLM did not provide granular citations for them:

{uncited_links}
"""

    content = f"""---
type: reference
status: current
date: {note_date}
source: "notebooklm:{args.slug}"
related:
  - "[[{dashboard_path}]]"
---

# {args.title}

{resolved}

---

{verbatim_section}

---

## Sources Referenced

{cited_links}
{uncited_section}"""

    output_path = VAULT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"CREATED: {args.output} ({len(resolved)} chars, {stats['cited_sources']}/{stats['total_sources']} sources cited)")


if __name__ == "__main__":
    main()
