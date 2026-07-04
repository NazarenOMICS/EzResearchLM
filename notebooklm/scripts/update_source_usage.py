#!/usr/bin/env python3
"""Update source notes with explicit QA usage metadata.

Writes/updates frontmatter fields on every source note in the notebook:
- used_in_qa: true|false
- cited_in_count: N
- qa_notes:
  - "[[Notes/...]]"

This makes it explicit whether a source was actually cited in exported QA notes,
independent of whether the source has a Source Guide.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VAULT = Path.cwd()


def safe_filename(title: str) -> str:
    title = re.sub(r'[/:*?"<>|]', '-', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 120:
        title = title[:120].rstrip(' -')
    return title


def parse_frontmatter(content: str) -> tuple[list[str], str]:
    if not content.startswith('---\n'):
        return [], content
    parts = content.split('\n---\n', 1)
    if len(parts) != 2:
        return [], content
    frontmatter = parts[0].splitlines()[1:]
    body = parts[1]
    return frontmatter, body


def dump_frontmatter(lines: list[str], body: str) -> str:
    return '---\n' + '\n'.join(lines).rstrip() + '\n---\n\n' + body.lstrip('\n')


def replace_frontmatter_block(lines: list[str], key: str, replacement: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(f'{key}:'):
            i += 1
            while i < len(lines) and (lines[i].startswith('  - ') or lines[i].startswith('    ')):
                i += 1
            out.extend(replacement)
            continue
        out.append(line)
        i += 1
    if not any(line.startswith(f'{key}:') for line in out):
        out.extend(replacement)
    return out


def note_to_wikilink(note_path: str) -> str:
    norm = note_path.replace('\\', '/')
    return f'[[{norm}]]'


def main() -> None:
    parser = argparse.ArgumentParser(description='Update source note usage metadata from QA notes')
    parser.add_argument('--sources', required=True, help='notebooklm source list JSON')
    parser.add_argument('--slug', required=True, help='Notebook slug')
    parser.add_argument('--qa-note', nargs='*', default=[], help='Vault-relative QA notes to scan')
    args = parser.parse_args()

    with open(args.sources, encoding='utf-8-sig') as f:
        sources_data = json.load(f)

    source_titles: dict[str, str] = {}
    for source in sources_data.get('sources', []):
        title = (source.get('title') or '').strip()
        if not title or title == '- YouTube':
            continue
        if (source.get('status') or '').strip().lower() not in {'', 'ready'}:
            continue
        source_titles[source['id']] = title

    cited_by_title: dict[str, list[str]] = {title: [] for title in source_titles.values()}
    source_link_re = re.compile(rf'\[\[Notes/NotebookLM/{re.escape(args.slug)}/Sources/([^\]#|]+)')
    pdf_link_re = re.compile(r'\[\[Research/Papers/([^\]#|]+)')

    for qa_note in args.qa_note:
        qa_path = VAULT / qa_note
        if not qa_path.exists():
            continue
        content = qa_path.read_text(encoding='utf-8')
        for marker in ('\n## Sources Referenced', '\n## Uncited Sources'):
            idx = content.find(marker)
            if idx != -1:
                content = content[:idx]
                break
        mentioned = set(m.group(1) for m in source_link_re.finditer(content))
        mentioned.update(m.group(1) for m in pdf_link_re.finditer(content))
        for title in mentioned:
            if title in cited_by_title:
                cited_by_title[title].append(qa_note)

    sources_dir = VAULT / 'Notes' / 'NotebookLM' / args.slug / 'Sources'
    updated = 0
    skipped_dirty = 0
    for title in sorted(source_titles.values()):
        source_file = sources_dir / (safe_filename(title) + '.md')
        if not source_file.exists():
            continue
        content = source_file.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        if not frontmatter:
            continue

        qa_notes = sorted(set(cited_by_title.get(title, [])))
        used = bool(qa_notes)

        # Dirty check: skip rewrite if nothing actually changed
        current_used = next((l.split(': ', 1)[1].strip() for l in frontmatter if l.startswith('used_in_qa:')), None)
        current_count = next((l.split(': ', 1)[1].strip() for l in frontmatter if l.startswith('cited_in_count:')), None)
        new_used = str(used).lower()
        new_count = str(len(qa_notes))
        if current_used == new_used and current_count == new_count:
            skipped_dirty += 1
            continue

        frontmatter = replace_frontmatter_block(frontmatter, 'used_in_qa', [f'used_in_qa: {new_used}'])
        frontmatter = replace_frontmatter_block(frontmatter, 'cited_in_count', [f'cited_in_count: {new_count}'])
        qa_block = ['qa_notes:'] + [f'  - "{note_to_wikilink(note)}"' for note in qa_notes] if qa_notes else ['qa_notes: []']
        frontmatter = replace_frontmatter_block(frontmatter, 'qa_notes', qa_block)

        source_file.write_text(dump_frontmatter(frontmatter, body), encoding='utf-8')
        updated += 1

    print(f'Updated source usage metadata: {updated} source notes', file=sys.stderr)
    if skipped_dirty:
        print(f'  Skipped (unchanged): {skipped_dirty}', file=sys.stderr)


if __name__ == '__main__':
    main()
