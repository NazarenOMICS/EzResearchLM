#!/usr/bin/env python3
"""Run a batch of NotebookLM questions and export all results to the vault."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPTS_DIR = Path(__file__).parent
VAULT = Path.cwd()


def _to_windows_path(path: Path) -> str:
    raw = str(path)
    if raw.startswith("/mnt/") and len(raw) > 6:
        drive = raw[5].upper()
        rest = raw[6:].replace("/", "\\")
        return f"{drive}:{rest}"
    return raw


def _powershell_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def wrap_windows_cli(cmd: list[str]) -> list[str]:
    if shutil.which(cmd[0]):
        return cmd
    if os.name != "nt" and shutil.which("powershell.exe") and cmd[0] == 'notebooklm':
        vault_win = _to_windows_path(VAULT)
        exe = os.environ.get('NOTEBOOKLM_EXE', 'notebooklm')
        arg_lines = '; '.join(f"$a += {_powershell_quote(part)}" for part in cmd[1:])
        wrapped = (
            f"Set-Location {_powershell_quote(vault_win)}; "
            f"$a = @(); {arg_lines}; "
            f"& {_powershell_quote(exe)} @a"
        )
        return ["powershell.exe", "-NoProfile", "-Command", wrapped]
    if os.name != "nt" and shutil.which("cmd.exe"):
        vault_win = _to_windows_path(VAULT)
        cmd_name = cmd[0]
        quoted = subprocess.list2cmdline([cmd_name, *cmd[1:]])
        wrapped = f"cd /d {vault_win} && {quoted}"
        return ["cmd.exe", "/C", wrapped]
    if os.name != "nt" and shutil.which("powershell.exe"):
        vault_win = _to_windows_path(VAULT)
        ps_args = " ".join(_powershell_quote(part) for part in cmd)
        wrapped = f"Set-Location {_powershell_quote(vault_win)}; & {ps_args}"
        return ["powershell.exe", "-NoProfile", "-Command", wrapped]
    return cmd


_STDERR_MAX_LINES = 25
_STDERR_MAX_CHARS = 1200


def run_cmd(cmd: list[str], label: str) -> tuple[int, str]:
    print(f"\n[{label}]", file=sys.stderr)
    real_cmd = wrap_windows_cli(cmd)
    result = subprocess.run(
        real_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stderr.strip():
        lines = result.stderr.strip().splitlines()
        if len(lines) > _STDERR_MAX_LINES:
            omitted = len(lines) - _STDERR_MAX_LINES
            lines = [f"  [...{omitted} lines omitted...]"] + lines[-_STDERR_MAX_LINES:]
        out = "\n".join(lines)
        if len(out) > _STDERR_MAX_CHARS:
            out = out[:_STDERR_MAX_CHARS] + f"\n  [...truncated at {_STDERR_MAX_CHARS} chars]"
        print(out, file=sys.stderr)
    if result.returncode != 0:
        print(f"  EXIT {result.returncode}: {' '.join(str(c) for c in real_cmd[:4])}", file=sys.stderr)
    return result.returncode, result.stdout


def safe_title(text: str, max_len: int = 60) -> str:
    cleaned = " ".join(text.strip().rstrip("?").split())
    return cleaned[:max_len] if len(cleaned) > max_len else cleaned


def short_slug(text: str, max_words: int = 6) -> str:
    import re
    import unicodedata
    normalized = unicodedata.normalize('NFD', text.lower())
    ascii_text = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    words = re.findall(r"[a-z0-9]+", ascii_text)
    skip = {'que', 'como', 'cual', 'cuales', 'son', 'las', 'los', 'de', 'en', 'el',
            'la', 'un', 'una', 'y', 'o', 'a', 'the', 'of', 'in', 'and', 'for', 'are', 'is'}
    words = [w for w in words if w not in skip]
    if not words:
        return 'qa'
    words = [w[:18] for w in words[:max_words]]
    return '-'.join(words)


def file_safe_slug(text: str) -> str:
    safe = text.replace("\\", "/").strip("/").replace("/", "__")
    return safe or "notebook"


def ask_question(question: str, qa_path: Path, notebook_id: str = "") -> bool:
    history_cmd = ["notebooklm", "history", "--clear"]
    if notebook_id:
        history_cmd += ["--notebook", notebook_id]
    run_cmd(history_cmd, "history | clear")
    ask_cmd = ["notebooklm", "ask", "--json"]
    if notebook_id:
        ask_cmd += ["--notebook", notebook_id]
    ask_cmd.append(question)
    code, stdout = run_cmd(ask_cmd, f"ask | {question[:70]}")
    if code != 0 or not stdout.strip():
        return False

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(f"  JSON error: {exc}", file=sys.stderr)
        return False

    refs = len(data.get("references", []))
    answer_len = len(data.get("answer", ""))
    print(f"  OK - {answer_len} chars, {refs} references", file=sys.stderr)
    qa_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def extract_passages(qa_files: list[str], sources_path: str, slug: str, tmp_dir: Path) -> Path | None:
    passage_map_path = tmp_dir / f"passage-map-{file_safe_slug(slug)}.json"
    code, _stdout = run_cmd(
        [
            sys.executable,
            str(SCRIPTS_DIR / "extract_passages.py"),
            "--qa",
            *qa_files,
            "--sources",
            sources_path,
            "--slug",
            slug,
            "--output",
            str(passage_map_path),   # write directly to file, never to stdout
        ],
        "extract_passages",
    )
    if code != 0 or not passage_map_path.exists():
        print("  WARNING: extract_passages failed - citations will link to source only.", file=sys.stderr)
        return None
    print(f"  Passage map -> {passage_map_path}", file=sys.stderr)
    return passage_map_path


def resolve_citations(
    qa_file: str,
    sources_path: str,
    slug: str,
    note_title: str,
    dashboard: str,
    output_path: str,
    note_date: str,
    passage_map_path: Path | None,
) -> bool:
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "resolve_citations.py"),
        "--qa",
        qa_file,
        "--sources",
        sources_path,
        "--slug",
        slug,
        "--title",
        note_title,
        "--dashboard",
        dashboard,
        "--output",
        output_path,
        "--date",
        note_date,
    ]
    if passage_map_path:
        cmd += ["--passages", str(passage_map_path)]

    code, _stdout = run_cmd(cmd, f"resolve | {note_title[:50]}")
    return code == 0


def update_source_usage(sources_path: str, slug: str, qa_notes: list[str]) -> bool:
    if not qa_notes:
        return False
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / 'update_source_usage.py'),
        '--sources',
        sources_path,
        '--slug',
        slug,
        '--qa-note',
        *qa_notes,
    ]
    code, _stdout = run_cmd(cmd, 'update_source_usage')
    return code == 0


def compile_qa_summary(questions_path: str, slug: str, dashboard: str, note_date: str) -> str | None:
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / 'compile_qa_summary.py'),
        '--questions',
        questions_path,
        '--slug',
        slug,
        '--dashboard',
        dashboard,
        '--date',
        note_date,
    ]
    code, stdout = run_cmd(cmd, 'compile_qa_summary')
    if code != 0:
        return None
    return stdout.strip() or None


def compile_source_curation(sources_path: str, slug: str, dashboard: str, note_date: str) -> str | None:
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / 'compile_source_curation.py'),
        '--sources',
        sources_path,
        '--slug',
        slug,
        '--dashboard',
        dashboard,
        '--date',
        note_date,
    ]
    code, stdout = run_cmd(cmd, 'compile_source_curation')
    if code != 0:
        return None
    return stdout.strip() or None


def audit_qa_citations(questions_path: str, slug: str, dashboard: str, note_date: str) -> str | None:
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / 'audit_qa_citations.py'),
        '--questions',
        questions_path,
        '--slug',
        slug,
        '--dashboard',
        dashboard,
        '--date',
        note_date,
    ]
    code, stdout = run_cmd(cmd, 'audit_qa_citations')
    if code != 0:
        return None
    return stdout.strip() or None


def compile_block_summary(slug: str, dashboard: str, note_date: str, title: str, qa_notes: list[str]) -> str | None:
    if not qa_notes:
        return None
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / 'compile_block_summary.py'),
        '--slug',
        slug,
        '--title',
        title,
        '--dashboard',
        dashboard,
        '--date',
        note_date,
        '--qa-note',
        *qa_notes,
    ]
    code, stdout = run_cmd(cmd, 'compile_block_summary')
    if code != 0:
        return None
    return stdout.strip() or None


STEPS = ["ask", "extract", "resolve", "compile"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ask NotebookLM and export to vault")
    parser.add_argument("--questions", required=True, help="Filled questions JSON")
    parser.add_argument("--sources", required=True, help="Output of notebooklm source list --json")
    parser.add_argument("--date", default=None, help="Date for note filenames (default: today)")
    parser.add_argument("--tmp-dir", default="/tmp", help="Directory for intermediate QA JSON files")
    parser.add_argument("--notebook-id", default="", help="NotebookLM notebook UUID â€” required to ensure questions go to the right notebook")
    parser.add_argument("--block-summary-title", default=None, help="Optional title for an auto-generated Block Summary note")
    parser.add_argument(
        "--from-step",
        choices=STEPS,
        default="ask",
        help="Resume pipeline from this step (ask|extract|resolve|compile). "
             "Skipped steps reuse existing files in --tmp-dir.",
    )
    args = parser.parse_args()

    note_date = args.date or date.today().isoformat()
    tmp_dir = Path(args.tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    from_idx = STEPS.index(args.from_step)

    questions_path = Path(args.questions)
    with open(questions_path, encoding="utf-8-sig") as handle:
        data = json.load(handle)

    slug = data["slug"]
    vault_slug = (data.get("vault_slug") or slug).replace("\\", "/").strip("/")
    dashboard = data.get("dashboard", slug.replace("-", " ").title())
    questions = data["questions"]

    if from_idx == 0:
        pending = [item for item in questions if item.get("status") == "pending" and item.get("question")]
    else:
        # Resuming: treat done+error questions as the active set
        pending = [item for item in questions if item.get("question")]

    if not pending:
        print("No questions found. Fill in the questions JSON first.", file=sys.stderr)
        sys.exit(1)

    notebook_id = args.notebook_id or data.get("notebook_id", "")
    print(f"Notebook: {slug} | ID: {notebook_id or '(not set â€” will use active notebook)'}", file=sys.stderr)
    if not notebook_id:
        print("  WARNING: --notebook-id not set. Questions may go to the wrong notebook.", file=sys.stderr)
    print(f"Questions: {len(pending)} | from-step: {args.from_step}", file=sys.stderr)
    print(f"Vault: {VAULT}", file=sys.stderr)

    print("\n=== STEP 1: Ask questions ===", file=sys.stderr)
    qa_files: list[str] = []
    if from_idx <= STEPS.index("ask"):
        for question in pending:
            qa_path = tmp_dir / f"qa-{question['id']}.json"
            success = ask_question(question["question"], qa_path, notebook_id=notebook_id)
            question["status"] = "done" if success else "error"
            question["qa_file"] = str(qa_path) if success else None
            if success:
                qa_files.append(str(qa_path))
        # Write once after the loop (not per question) â€” N fewer writes
        questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        if not qa_files:
            print("\nAll questions failed. Check NotebookLM auth with a real command: notebooklm list", file=sys.stderr)
            sys.exit(1)
        print(f"\n{len(qa_files)}/{len(pending)} questions answered", file=sys.stderr)
    else:
        # Reuse existing QA files from tmp_dir
        for question in pending:
            qa_path = tmp_dir / f"qa-{question['id']}.json"
            if qa_path.exists():
                question["qa_file"] = str(qa_path)
                qa_files.append(str(qa_path))
        print(f"  Reusing {len(qa_files)} existing QA files from {tmp_dir}", file=sys.stderr)

    print("\n=== STEP 2: Extract passages ===", file=sys.stderr)
    if from_idx <= STEPS.index("extract"):
        passage_map_path = extract_passages(qa_files, args.sources, vault_slug, tmp_dir)
    else:
        # Reuse existing passage map
        existing_pm = tmp_dir / f"passage-map-{file_safe_slug(vault_slug)}.json"
        passage_map_path = existing_pm if existing_pm.exists() else None
        print(f"  Reusing passage map: {passage_map_path}", file=sys.stderr)

    print("\n=== STEP 3: Resolve citations -> vault ===", file=sys.stderr)
    qa_dir = VAULT / "Notes" / "NotebookLM" / vault_slug / "QA"
    answers_dir = qa_dir / 'answers'
    summaries_dir = qa_dir / 'summaries'
    answers_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    exported = 0
    exported_notes: list[str] = []
    if from_idx <= STEPS.index("resolve"):
        for question in pending:
            if not question.get("qa_file"):
                continue

            full_question = question['question'].strip()
            qid = question['id']
            id_str = f"{qid:02d}" if isinstance(qid, int) else str(qid)
            note_title = f"Q{id_str} - {full_question}"
            note_slug = short_slug(full_question)
            output_path = f"Notes/NotebookLM/{vault_slug}/QA/answers/{note_date} Q{id_str} - {note_slug}.md"
            if resolve_citations(
                qa_file=question["qa_file"],
                sources_path=args.sources,
                slug=vault_slug,
                note_title=note_title,
                dashboard=dashboard,
                output_path=output_path,
                note_date=note_date,
                passage_map_path=passage_map_path,
            ):
                question["vault_note"] = output_path
                exported_notes.append(output_path)
                exported += 1
    else:
        # Reuse vault_note paths already stored in questions JSON
        for question in pending:
            vn = question.get("vault_note")
            if vn and (VAULT / vn).exists():
                exported_notes.append(vn)
                exported += 1
        print(f"  Reusing {exported} existing vault notes", file=sys.stderr)

    summary_note = None
    source_curation_note = None
    block_summary_note = None
    citation_audit_note = None

    # Persist vault_note fields before downstream summary compilers read the questions JSON
    questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if exported_notes:
        data["vault_slug"] = vault_slug
        questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        update_source_usage(args.sources, vault_slug, exported_notes)
        summary_note = compile_qa_summary(str(questions_path), vault_slug, dashboard, note_date)
        source_curation_note = compile_source_curation(args.sources, vault_slug, dashboard, note_date)
        citation_audit_note = audit_qa_citations(str(questions_path), vault_slug, dashboard, note_date)
        if args.block_summary_title:
            block_summary_note = compile_block_summary(vault_slug, dashboard, note_date, args.block_summary_title, exported_notes)
        if summary_note:
            data["qa_summary_note"] = summary_note
        if source_curation_note:
            data["source_curation_note"] = source_curation_note
        if citation_audit_note:
            data["citation_audit_note"] = citation_audit_note
        if block_summary_note:
            data["block_summary_note"] = block_summary_note

    questions_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 40}", file=sys.stderr)
    print(f"  Questions asked : {len(qa_files)}/{len(pending)}", file=sys.stderr)
    print(f"  Notes exported  : {exported}", file=sys.stderr)
    if summary_note:
        print(f"  QA summary      : {summary_note}", file=sys.stderr)
    if source_curation_note:
        print(f"  Source curation : {source_curation_note}", file=sys.stderr)
    if citation_audit_note:
        print(f"  Citation audit  : {citation_audit_note}", file=sys.stderr)
    if block_summary_note:
        print(f"  Block summary   : {block_summary_note}", file=sys.stderr)
    print(f"  Vault path      : Notes/NotebookLM/{vault_slug}/QA/", file=sys.stderr)
    if exported:
        print("\nNext steps:", file=sys.stderr)
        print(f'  cd "{VAULT}" && qmd update', file=sys.stderr)
    print(f"{'=' * 40}", file=sys.stderr)


if __name__ == "__main__":
    main()

