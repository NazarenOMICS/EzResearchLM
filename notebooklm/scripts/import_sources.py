#!/usr/bin/env python3
"""Import NotebookLM sources into vault as notebook-source files.

Usage:
  python3 import_sources.py --sources /tmp/sources.json --slug my-notebook --dashboard "Dashboard Title"
  python3 import_sources.py --sources /tmp/sources.json --slug my-notebook --dashboard "Dashboard Title" --skip-guides
  python3 import_sources.py --sources /tmp/sources.json --slug my-notebook --dashboard "Dashboard Title" --papers-dir /path/to/pdfs

Must run from vault root (uses Path.cwd() as VAULT root).

With --papers-dir: matches PDFs to sources by author surname + year heuristic,
copies matches to Research/Papers/, and embeds them in the source .md file.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VAULT = Path.cwd()  # Expected to run from vault root


def _to_windows_path(path: Path) -> str:
    raw = str(path)
    if raw.startswith("/mnt/") and len(raw) > 6:
        drive = raw[5].upper()
        rest = raw[6:].replace("/", "\\")
        return f"{drive}:{rest}"
    return raw


def _powershell_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def run_notebooklm(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    command = ["notebooklm", *args]
    if shutil.which("notebooklm"):
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    if os.name != "nt" and shutil.which("powershell.exe"):
        vault_win = _to_windows_path(VAULT)
        ps_args = " ".join(_powershell_quote(part) for part in command)
        wrapped = f"Set-Location {_powershell_quote(vault_win)}; & {ps_args}"
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", wrapped],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    if os.name != "nt" and shutil.which("cmd.exe"):
        vault_win = _to_windows_path(VAULT)
        quoted = subprocess.list2cmdline(command)
        wrapped = f"cd /d {vault_win} && {quoted}"
        return subprocess.run(
            ["cmd.exe", "/C", wrapped],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    raise FileNotFoundError("notebooklm not found in PATH and Windows fallback unavailable")

TYPE_MAP = {
    "SourceType.YOUTUBE":       "youtube",
    "SourceType.WEB_PAGE":      "web",
    "SourceType.PDF":           "pdf",
    "SourceType.TEXT":          "text",
    "SourceType.GOOGLE_DOCS":   "gdocs",
    "SourceType.GOOGLE_SLIDES": "gslides",
}

BAD_TITLE_PATTERNS = [
    r"^attention required!\s*\|\s*cloudflare$",
    r"^validate user$",
    r"^checking your browser.*recaptcha$",
    r"^https?://.+$",
]


def safe_filename(title: str) -> str:
    title = re.sub(r'[/:*?"<>|]', '-', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > 120:
        title = title[:120].rstrip(' -')
    return title


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


def dedupe_sources(sources: list[dict]) -> list[dict]:
    def score(item: dict) -> tuple[int, int]:
        source_type = TYPE_MAP.get(item.get("type", ""), "web")
        type_score = 1 if source_type == "pdf" else 0
        url_score = 1 if item.get("url") else 0
        return (type_score, url_score)

    deduped: dict[tuple[str, str], dict] = {}
    for source in sources:
        if should_skip_source(source):
            continue
        title = safe_filename((source.get("title") or "").strip()).lower()
        url = (source.get("url") or "").strip().lower()
        key = (title, url)
        current = deduped.get(key)
        if current is None or score(source) > score(current):
            deduped[key] = source
    return list(deduped.values())


def fetch_guide(source_id: str) -> tuple[str, list[str], list[str]]:
    """Fetch AI-generated source guide. Returns (summary, topics, keywords)."""
    try:
        result = run_notebooklm(["source", "guide", source_id, "--json"], timeout=60)
        if result.returncode != 0:
            return "", [], []
        data = json.loads(result.stdout)
        return data.get("summary", ""), data.get("topics", []), data.get("keywords", [])
    except Exception:
        return "", [], []


# ---------------------------------------------------------------------------
# PDF matching helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, remove punctuation, collapse spaces."""
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', text.lower())).strip()


def _extract_year(text: str) -> str | None:
    """Return first 4-digit year (1900-2030) found in text, or None."""
    m = re.search(r'\b(19\d{2}|20[0-2]\d)\b', text)
    return m.group(1) if m else None


def _first_word(text: str) -> str:
    """Return first alphabetic word (likely author surname)."""
    m = re.search(r'[a-z]+', _normalize(text))
    return m.group(0) if m else ""


def find_matching_pdf(title: str, pdf_files: list[Path]) -> Path | None:
    """
    Match a source title to a PDF by author+year heuristic.

    A PDF matches if its lowercased filename contains BOTH:
      - the first word of the title (expected: author surname)
      - the 4-digit year found in the title

    Returns the single best match or None if 0 or >1 matches.
    """
    normalized_title = _normalize(title)
    exact_name_matches = [
        p for p in pdf_files
        if _normalize(p.name) == normalized_title or _normalize(p.stem) == normalized_title
    ]
    if len(exact_name_matches) == 1:
        return exact_name_matches[0]

    year   = _extract_year(title)
    author = _first_word(title)

    if not year or not author:
        return None

    matches = [
        p for p in pdf_files
        if author in p.name.lower() and year in p.name
    ]

    return matches[0] if len(matches) == 1 else None


def normalize_vault_subdir(raw: str) -> str:
    cleaned = (raw or "Research/Papers").replace("\\", "/").strip("/")
    parts = [part for part in cleaned.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise ValueError(f"Unsafe vault subdir: {raw}")
    return "/".join(parts) if parts else "Research/Papers"


def embed_pdf(title: str, papers_dir: Path, pdf_files: list[Path], papers_vault_subdir: str) -> tuple[str, str | None]:
    """
    Try to find and copy the PDF for this source.

    Returns:
      (embed_block, vault_relative_path)  if found
      ("", None)                          if not found
    """
    pdf = find_matching_pdf(title, pdf_files)
    if pdf is None:
        return "", None

    papers_vault_subdir = normalize_vault_subdir(papers_vault_subdir)
    papers_vault_dir = VAULT / papers_vault_subdir
    papers_vault_dir.mkdir(parents=True, exist_ok=True)
    dest = papers_vault_dir / pdf.name

    if not dest.exists():
        try:
            shutil.copy2(pdf, dest)
        except PermissionError:
            shutil.copyfile(pdf, dest)
        print(f"    PDF copied: {papers_vault_subdir}/{pdf.name}", file=sys.stderr)
    else:
        print(f"    PDF exists: {papers_vault_subdir}/{pdf.name}", file=sys.stderr)

    vault_rel = f"{papers_vault_subdir}/{pdf.name}"
    embed = f"![[{vault_rel}]]"
    return embed, vault_rel


def extract_existing_cited_passages(filepath: Path) -> str:
    if not filepath.exists():
        return ""
    content = filepath.read_text(encoding="utf-8")
    marker = "\n## Cited Passages"
    idx = content.find(marker)
    if idx == -1:
        return ""
    return content[idx:].rstrip() + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import NotebookLM sources into vault")
    parser.add_argument("--sources",    required=True, help="Path to notebooklm source list JSON")
    parser.add_argument("--slug",       required=True, help="Notebook slug (kebab-case folder name)")
    parser.add_argument("--vault-slug", default=None,
                        help="Vault-relative notebook folder under Notes/NotebookLM (can include project/category)")
    parser.add_argument("--project", default="general", help="Project/category label for frontmatter")
    parser.add_argument("--dashboard",  required=True, help="Dashboard title for related links")
    parser.add_argument("--skip-guides", action="store_true", help="Skip fetching AI source guides")
    parser.add_argument("--refresh-existing", action="store_true",
                        help="Rewrite existing source notes instead of skipping them")
    parser.add_argument("--papers-dir", default=None,
                        help="Directory containing PDFs to embed (matched by author+year)")
    parser.add_argument("--papers-vault-subdir", default="Research/Papers",
                        help="Vault-relative folder where matched PDFs are copied")
    args = parser.parse_args()

    with open(args.sources, encoding="utf-8-sig") as f:
        data = json.load(f)

    notebook_id  = data.get("notebook_id", "")
    sources      = dedupe_sources(data["sources"])
    vault_slug   = (args.vault_slug or args.slug).replace("\\", "/").strip("/")
    sources_dir  = VAULT / "Notes" / "NotebookLM" / vault_slug / "Sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path = f"Notes/Dashboards/{args.dashboard}"

    # Pre-collect PDFs if --papers-dir given
    pdf_files: list[Path] = []
    if args.papers_dir:
        pdf_dir = Path(args.papers_dir)
        if not pdf_dir.exists():
            print(f"WARNING: --papers-dir not found: {pdf_dir}", file=sys.stderr)
        else:
            pdf_files = list(pdf_dir.glob("*.pdf"))
            print(f"PDF candidates: {len(pdf_files)}", file=sys.stderr)

    created = 0
    skipped = 0
    embedded = 0
    filtered_out = len(data["sources"]) - len(sources)

    if filtered_out:
        print(f"Filtered out: {filtered_out} low-quality/duplicate sources", file=sys.stderr)

    for source in sources:
        title       = source["title"].strip()
        source_id   = source["id"]
        source_type = TYPE_MAP.get(source["type"], "web")
        url         = source.get("url") or ""
        doc_date    = source.get("created_at", "")[:10]

        filename = safe_filename(title) + ".md"
        filepath = sources_dir / filename
        existed_before = filepath.exists()
        cited_passages = extract_existing_cited_passages(filepath) if existed_before else ""

        if existed_before and not args.refresh_existing:
            print(f"  EXISTS: {filename}", file=sys.stderr)
            skipped += 1
            continue

        # Fetch source guide
        guide_text = ""
        keywords   = []
        if not args.skip_guides:
            print(f"  Guide: {title[:60]}...", file=sys.stderr)
            summary, topics, keywords = fetch_guide(source_id)
            if summary:
                guide_text = summary
                if topics:
                    guide_text += "\n\n### Topics\n\n" + ", ".join(topics)
                print(f"    {len(summary)} chars, {len(keywords)} keywords", file=sys.stderr)
            else:
                print(f"    WARN: no guide returned", file=sys.stderr)

        # Match PDF
        pdf_embed = ""
        pdf_frontmatter = ""
        if pdf_files:
            pdf_embed, pdf_rel = embed_pdf(title, Path(args.papers_dir), pdf_files, args.papers_vault_subdir)
            if pdf_rel:
                pdf_frontmatter = f'pdf: "{pdf_rel}"\n'
                embedded += 1

        # Build topics frontmatter
        topics_yaml = ""
        if keywords:
            topics_yaml = "topics:\n" + "\n".join(f'  - "[[{k}]]"' for k in keywords) + "\n"

        # PDF embed block goes right before the Source Guide section
        pdf_section = f"\n## PDF\n\n{pdf_embed}\n" if pdf_embed else ""

        content = f"""---
type: notebook-source
source_id: "{source_id}"
notebook_id: "{notebook_id}"
slug: "{args.slug}"
vault_slug: "{vault_slug}"
project: "{args.project}"
url: "{url}"
source_type: {source_type}
status: active
date: {doc_date}
{pdf_frontmatter}{topics_yaml}related:
  - "[[{dashboard_path}]]"
---

# {title}
{pdf_section}
## Source Guide

{guide_text}
"""

        if cited_passages:
            content = content.rstrip() + "\n" + cited_passages

        filepath.write_text(content, encoding="utf-8")
        action = "UPDATED" if existed_before else "CREATED"
        print(f"  {action}: {filename}", file=sys.stderr)
        created += 1

    # stdout: single summary line only (contract)
    print(f"Done: {created} created/updated, {skipped} skipped, {embedded} PDFs embedded")


if __name__ == "__main__":
    main()
