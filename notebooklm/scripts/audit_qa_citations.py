#!/usr/bin/env python3
"""Audit exported QA citation links without using a model."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VAULT = Path.cwd()


def qa_notes_from_questions(path: Path) -> list[str]:
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    notes: list[str] = []
    for item in data.get("questions", []):
        note = item.get("vault_note")
        if note:
            notes.append(note.replace("\\", "/"))
    return notes


def strip_reference_sections(text: str) -> str:
    for marker in (
        "\n---\n\n## Extractos citados verbatim",
        "\n## Extractos citados verbatim",
        "\n## Sources Referenced",
        "\n## Uncited Sources",
    ):
        idx = text.find(marker)
        if idx != -1:
            return text[:idx]
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit exported QA citation links")
    parser.add_argument("--questions", required=True, help="Filled questions JSON")
    parser.add_argument("--slug", required=True, help="Notebook slug")
    parser.add_argument("--dashboard", required=True, help="Dashboard title")
    parser.add_argument("--date", default=None, help="Date for note filename")
    args = parser.parse_args()

    note_date = args.date or date.today().isoformat()
    qa_notes = qa_notes_from_questions(Path(args.questions))
    sources_dir = VAULT / "Notes" / "NotebookLM" / args.slug / "Sources"

    total_source_links = 0
    total_passage_links = 0
    total_pdf_links = 0
    broken_sources: set[str] = set()
    notes_without_source_links: list[str] = []

    source_re = re.compile(rf"\[\[Notes/NotebookLM/{re.escape(args.slug)}/Sources/([^\]#|]+)(#[^\]|]+)?")
    pdf_re = re.compile(r"\[\[Research/Papers/([^\]#|]+)")

    for qa_note in qa_notes:
        path = VAULT / qa_note
        if not path.exists():
            notes_without_source_links.append(f"{qa_note} (missing QA note)")
            continue
        content = strip_reference_sections(path.read_text(encoding="utf-8"))
        source_matches = list(source_re.finditer(content))
        pdf_matches = list(pdf_re.finditer(content))
        total_source_links += len(source_matches)
        total_passage_links += sum(1 for m in source_matches if m.group(2))
        total_pdf_links += len(pdf_matches)
        if not source_matches:
            notes_without_source_links.append(qa_note)
        for match in source_matches:
            source_name = match.group(1)
            if not (sources_dir / f"{source_name}.md").exists():
                broken_sources.add(source_name)

    status = "pass"
    if broken_sources or notes_without_source_links:
        status = "fail"
    elif total_pdf_links:
        status = "warn"

    dashboard_path = f"Notes/Dashboards/{args.dashboard}"
    output_rel = f"Notes/NotebookLM/{args.slug}/QA/summaries/{note_date} Citation Audit.md"
    output = VAULT / output_rel
    output.parent.mkdir(parents=True, exist_ok=True)

    broken_block = "\n".join(f"- {name}" for name in sorted(broken_sources)) or "- None"
    notes_block = "\n".join(f"- [[{note}]]" for note in notes_without_source_links) or "- None"

    content = f"""---
type: citation-audit
status: {status}
date: {note_date}
source: "notebooklm:{args.slug}:citation-audit"
related:
  - "[[{dashboard_path}]]"
---

# Citation Audit - {args.slug}

## Verdict

- Status: {status.upper()}
- QA notes checked: {len(qa_notes)}
- Source links: {total_source_links}
- Passage-anchored links: {total_passage_links}
- PDF links in QA body: {total_pdf_links}

## Broken Source Links

{broken_block}

## QA Notes Without Source Links

{notes_block}

## Interpretation

- PASS means exported QA notes link claims to existing `Sources` notes.
- WARN means QA notes are traceable, but some body links still point directly to PDFs.
- FAIL means at least one QA note lacks source links or points to missing source notes.
"""
    output.write_text(content, encoding="utf-8")
    print(f"Created citation audit: {output_rel}", file=sys.stderr)
    print(output_rel)
    if status == "fail":
        sys.exit(1)


if __name__ == "__main__":
    main()
