#!/usr/bin/env python3
"""Large-corpus discovery workflow for NotebookLM.

Purpose:
- use NotebookLM's own search (`source add-research`) to ingest many candidate sources fast
- export source list JSON
- optionally mirror sources into the vault with import_sources.py

This is intended for broad literature blocks where 30-100+ sources and many
potential citations are more useful than a tiny hand-curated corpus.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

VAULT = Path.cwd()
SCRIPTS_DIR = Path(__file__).parent


def _to_windows_path(path: Path) -> str:
    raw = str(path)
    if raw.startswith('/mnt/') and len(raw) > 6:
        drive = raw[5].upper()
        rest = raw[6:].replace('/', '\\')
        return f'{drive}:{rest}'
    return raw


def _powershell_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def wrap_windows_cli(cmd: list[str]) -> list[str]:
    if shutil.which(cmd[0]):
        return cmd
    if os.name != 'nt' and shutil.which('powershell.exe'):
        vault_win = _to_windows_path(VAULT)
        ps_args = ' '.join(_powershell_quote(part) for part in cmd)
        wrapped = f"Set-Location {_powershell_quote(vault_win)}; & {ps_args}"
        return ['powershell.exe', '-NoProfile', '-Command', wrapped]
    if os.name != 'nt' and shutil.which('cmd.exe'):
        vault_win = _to_windows_path(VAULT)
        quoted = subprocess.list2cmdline(cmd)
        wrapped = f'cd /d {vault_win} && {quoted}'
        return ['cmd.exe', '/C', wrapped]
    return cmd


def run_cmd(cmd: list[str], label: str) -> tuple[int, str]:
    print(f'\n[{label}]', file=sys.stderr)
    real_cmd = wrap_windows_cli(cmd)
    result = subprocess.run(real_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        print(f"  EXIT {result.returncode}: {' '.join(str(c) for c in real_cmd[:4])}", file=sys.stderr)
    return result.returncode, result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description='Run NotebookLM large-corpus research workflow')
    parser.add_argument('--slug', required=True, help='Notebook slug for vault export')
    parser.add_argument('--dashboard', required=True, help='Dashboard title for vault notes')
    parser.add_argument('--query', required=True, help='Research query to run inside NotebookLM')
    parser.add_argument('--title', default=None, help='Notebook title (created if --notebook-id not provided)')
    parser.add_argument('--notebook-id', default=None, help='Use an existing notebook instead of creating one')
    parser.add_argument('--mode', default='deep', choices=['fast', 'deep'], help='NotebookLM research mode')
    parser.add_argument('--out-dir', default='/tmp', help='Directory for exported source list JSON')
    parser.add_argument('--skip-import', action='store_true', help='Do not mirror sources into the vault')
    parser.add_argument('--skip-guides', action='store_true', help='Pass --skip-guides to import_sources.py')
    args = parser.parse_args()

    notebook_id = args.notebook_id
    notebook_title = args.title or args.slug.replace('-', ' ').title()

    if not notebook_id:
        code, stdout = run_cmd(['notebooklm', 'create', notebook_title], 'create_notebook')
        if code != 0:
            sys.exit(code)
        line = next((line for line in stdout.splitlines() if 'Created notebook:' in line), '')
        if 'Created notebook:' not in line:
            print('ERROR: Could not parse notebook creation output', file=sys.stderr)
            sys.exit(1)
        notebook_id = line.split('Created notebook:', 1)[1].split('-', 1)[0].strip()

    code, _ = run_cmd(['notebooklm', 'use', notebook_id], 'use_notebook')
    if code != 0:
        sys.exit(code)

    code, _ = run_cmd([
        'notebooklm', 'source', 'add-research', args.query,
        '--mode', args.mode,
        '--import-all',
        '--no-wait',
    ], 'source_add_research')
    if code != 0:
        sys.exit(code)

    code, _ = run_cmd(['notebooklm', 'research', 'wait', '--import-all'], 'research_wait')
    if code != 0:
        sys.exit(code)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sources_json = out_dir / f'tmp-sources-{args.slug}.json'
    code, stdout = run_cmd(['notebooklm', 'source', 'list', '--json'], 'source_list_json')
    if code != 0:
        sys.exit(code)
    sources_json.write_text(stdout, encoding='utf-8')
    print(f'Sources JSON -> {sources_json}', file=sys.stderr)

    imported = False
    if not args.skip_import:
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / 'import_sources.py'),
            '--sources', str(sources_json),
            '--slug', args.slug,
            '--dashboard', args.dashboard,
        ]
        if args.skip_guides:
            cmd.append('--skip-guides')
        code, _ = run_cmd(cmd, 'import_sources')
        if code == 0:
            imported = True

    with open(sources_json, encoding='utf-8-sig') as f:
        payload = json.load(f)
    ready = sum(1 for s in payload.get('sources', []) if (s.get('status') or '').lower() == 'ready')
    errored = sum(1 for s in payload.get('sources', []) if (s.get('status') or '').lower() == 'error')

    print('\n' + '=' * 48, file=sys.stderr)
    print(f'Notebook ID      : {notebook_id}', file=sys.stderr)
    print(f'Notebook title   : {payload.get("notebook_title") or notebook_title}', file=sys.stderr)
    print(f'Sources total    : {payload.get("count", 0)}', file=sys.stderr)
    print(f'Sources ready    : {ready}', file=sys.stderr)
    print(f'Sources error    : {errored}', file=sys.stderr)
    print(f'Sources JSON     : {sources_json}', file=sys.stderr)
    print(f'Imported to vault: {imported}', file=sys.stderr)
    print('=' * 48, file=sys.stderr)


if __name__ == '__main__':
    main()
