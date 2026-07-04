#!/usr/bin/env python3
"""Compile a local source curation report from NotebookLM sources + QA usage metadata.

This report is designed for large-corpus mode:
- core sources = actually cited in QA
- review queue = imported/ready but not yet cited
- noisy or failed sources = likely discard

No model/API required. Purely local heuristics over source status and frontmatter.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

VAULT = Path.cwd()


def safe_filename(title: str) -> str:
    title = re.sub(r'[/:*?"<>|]', '-', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 120:
        title = title[:120].rstrip(' -')
    return title


def parse_frontmatter_map(path: Path) -> dict[str, str]:
    """Read only the YAML frontmatter block (stops at closing ---). Never reads body."""
    if not path.exists():
        return {}
    fm_lines: list[str] = []
    try:
        with open(path, encoding='utf-8') as fh:
            first = fh.readline()
            if first.rstrip('\n') != '---':
                return {}
            for line in fh:
                if line.rstrip('\n') == '---':
                    break
                fm_lines.append(line)
                if len(fm_lines) > 60:   # safety cap — frontmatter never this long
                    break
    except OSError:
        return {}
    data: dict[str, str] = {}
    for line in fm_lines:
        if ': ' in line and not line.startswith('  - '):
            key, value = line.split(': ', 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description='Compile local source curation report')
    parser.add_argument('--sources', required=True, help='notebooklm source list JSON')
    parser.add_argument('--slug', required=True, help='Notebook slug')
    parser.add_argument('--dashboard', required=True, help='Dashboard title')
    parser.add_argument('--date', default=None, help='Date for note')
    args = parser.parse_args()

    note_date = args.date or date.today().isoformat()
    with open(args.sources, encoding='utf-8-sig') as f:
        payload = json.load(f)

    sources_dir = VAULT / 'Notes' / 'NotebookLM' / args.slug / 'Sources'
    core: list[tuple[str, int, str]] = []
    review: list[str] = []
    noisy: list[str] = []

    for source in payload.get('sources', []):
        title = (source.get('title') or '').strip()
        status = (source.get('status') or '').strip().lower()
        if not title:
            continue
        if status == 'error':
            noisy.append(f'{title} (status=error)')
            continue
        note_path = sources_dir / (safe_filename(title) + '.md')
        fm = parse_frontmatter_map(note_path)
        used = fm.get('used_in_qa', 'false').lower() == 'true'
        cited_in_count = int(fm.get('cited_in_count', '0') or '0')
        source_type = source.get('type') or ''
        if used:
            core.append((title, cited_in_count, source_type))
        else:
            review.append(title)

    core.sort(key=lambda x: (-x[1], x[0].lower()))
    dashboard_path = f'Notes/Dashboards/{args.dashboard}'
    output_rel = f'Notes/NotebookLM/{args.slug}/QA/summaries/{note_date} Source Curation.md'
    output = VAULT / output_rel

    core_block = '\n'.join(
        f'- {title} - cited_in_count={count} - type={source_type}' for title, count, source_type in core
    ) or '- No core sources yet'
    review_block = '\n'.join(f'- {title}' for title in review) or '- No review sources'
    noisy_block = '\n'.join(f'- {title}' for title in noisy) or '- No noisy/error sources'

    content = f'''---
type: source-curation
status: current
date: {note_date}
source: "notebooklm:{args.slug}:source-curation"
related:
  - "[[{dashboard_path}]]"
---

# Source Curation - {args.slug}

Reporte local para corpus grande. Resume que fuentes ya demostraron valor real en QA y cuales conviene revisar o descartar.

## Core sources (cited in QA)

{core_block}

## Review queue (ready but not yet cited)

{review_block}

## Noisy / failed sources

{noisy_block}

## Regla practica de depuracion

- conservar primero las fuentes de `Core sources`
- revisar manualmente `Review queue` antes de descartarlas
- eliminar o ignorar `Noisy / failed sources` salvo que se reparen y vuelvan a entrar limpias
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    print(f'Created source curation report: {output_rel}', file=sys.stderr)
    print(output_rel)


if __name__ == '__main__':
    main()
