#!/usr/bin/env python3
"""Compile exported QA notes into a single notebook summary document.

Produces a deterministic, citation-preserving summary note that is useful for
thesis/introduction drafting:
- links to each QA note
- short extractive summary of each answer
- aggregated source usage table via dataviewjs
- consolidated list of gaps / missing coverage if present
"""
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


def strip_frontmatter(content: str) -> str:
    if not content.startswith('---\n'):
        return content
    parts = content.split('\n---\n', 1)
    return parts[1] if len(parts) == 2 else content


def extract_main_body(content: str) -> str:
    body = strip_frontmatter(content).strip()
    for marker in ('\n---\n\n## Extractos citados verbatim', '\n---\n\n## Sources Referenced'):
        idx = body.find(marker)
        if idx != -1:
            body = body[:idx].rstrip()
            break
    return body


def extract_summary_paragraph(body: str, max_chars: int = 1200) -> str:
    lines = [line.rstrip() for line in body.splitlines()]
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    paragraphs = [p.strip() for p in '\n'.join(lines).split('\n\n') if p.strip()]
    if not paragraphs:
        return ''
    text = paragraphs[0]
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + '...'
    return text


def extract_missing_section(body: str) -> str:
    for heading in ('### Información no cubierta y sugerencias de búsqueda', '## Información no cubierta y sugerencias de búsqueda'):
        idx = body.find(heading)
        if idx != -1:
            return body[idx:].strip()
    return ''


def collect_source_mentions(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    patterns = [
        r'\[\[Notes/NotebookLM/[^\]]+/Sources/([^\]#|]+)',
        r'\[\[Research/Papers/([^\]|]+)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1)
            counts[name] = counts.get(name, 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description='Compile QA notes into a summary note')
    parser.add_argument('--questions', required=True, help='questions JSON with vault_note entries')
    parser.add_argument('--slug', required=True, help='Notebook slug')
    parser.add_argument('--dashboard', required=True, help='Dashboard title')
    parser.add_argument('--date', default=None, help='Note date (default: today)')
    args = parser.parse_args()

    note_date = args.date or date.today().isoformat()
    with open(args.questions, encoding='utf-8') as f:
        payload = json.load(f)

    questions = payload.get('questions', [])
    qa_items = [q for q in questions if q.get('vault_note')]
    if not qa_items:
        print('No exported QA notes found in questions JSON', file=sys.stderr)
        sys.exit(1)

    sections: list[str] = []
    gaps: list[str] = []
    qa_dir = f'Notes/NotebookLM/{args.slug}/QA/summaries'
    sources_path = f'Notes/NotebookLM/{args.slug}/Sources'
    source_counts: dict[str, int] = {}

    for item in qa_items:
        note_path = item['vault_note']
        note_file = VAULT / note_path
        if not note_file.exists():
            continue
        content = note_file.read_text(encoding='utf-8')
        main_body = extract_main_body(content)
        summary = extract_summary_paragraph(main_body)
        missing = extract_missing_section(main_body)
        if missing:
            gaps.append(f'### Desde {item.get("id")}: {item.get("question") or "QA"}\n\n{missing}')
        for name, count in collect_source_mentions(main_body).items():
            source_counts[name] = source_counts.get(name, 0) + count
        sections.append(
            '\n'.join([
                f"## Q{int(item['id']):02d}" if isinstance(item['id'], int) else f"## {item['id']}",
                f"- Pregunta: {item.get('question') or ''}",
                f"- Nota completa: [[{note_path}]]",
                '',
                summary,
            ]).strip()
        )

    sorted_sources = sorted(source_counts.items(), key=lambda item: (-item[1], item[0].lower()))
    source_list = '\n'.join(
        f'- [[{sources_path}/{name}|{name}]] - {count} mencion(es)'
        for name, count in sorted_sources
    ) or '- Sin fuentes detectadas en el resumen'

    gaps_section = ''
    if gaps:
        gaps_section = '\n\n## Gaps detectados en QA\n\n' + '\n\n'.join(gaps)

    output_rel = f'{qa_dir}/{note_date} QA Summary.md'
    output = VAULT / output_rel
    dashboard_path = f'Notes/Dashboards/{args.dashboard}'
    content = f'''---
type: reference-summary
status: current
date: {note_date}
source: "notebooklm:{args.slug}:qa-summary"
related:
  - "[[{dashboard_path}]]"
---

# QA Summary - {args.slug}

Documento consolidado de las QA exportadas para este notebook. Util para redactar introducciones, comparar respuestas y localizar rapidamente que nota contiene cada argumento.

## QA incluidas

{chr(10).join(f'- [[{item["vault_note"]}]]' for item in qa_items if item.get("vault_note"))}

## Resumen por QA

{chr(10).join(sections)}

## Sources Referenced Across QA Summary

{source_list}{gaps_section}
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    print(f'Created QA summary: {output_rel}', file=sys.stderr)
    print(output_rel)


if __name__ == '__main__':
    main()
