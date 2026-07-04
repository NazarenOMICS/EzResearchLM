#!/usr/bin/env python3
"""Compile QA notes into a domain-agnostic block summary for thesis writing."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VAULT = Path.cwd()
SKIP_HEADINGS = {
    "extractos citados verbatim",
    "sources referenced",
    "uncited sources",
    "informacion no cubierta y sugerencias de busqueda",
}


def strip_frontmatter(content: str) -> str:
    if not content.startswith("---\n"):
        return content
    parts = content.split("\n---\n", 1)
    return parts[1] if len(parts) == 2 else content


def normalize_heading(text: str) -> str:
    normalized = text.strip().lower()
    normalized = normalized.translate(str.maketrans("áéíóúñ", "aeioun"))
    return normalized


def cut_before_aux_sections(body: str) -> str:
    for marker in (
        "\n---\n\n## Extractos citados verbatim",
        "\n---\n\n## Sources Referenced",
        "\n## Extractos citados verbatim",
        "\n## Sources Referenced",
        "\n## Uncited Sources",
    ):
        idx = body.find(marker)
        if idx != -1:
            return body[:idx].rstrip()
    return body.rstrip()


def extract_summary_paragraph(body: str, max_chars: int = 700) -> str:
    lines = [line.rstrip() for line in body.splitlines()]
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    paragraphs = [p.strip() for p in "\n".join(lines).split("\n\n") if p.strip()]
    if not paragraphs:
        return ""
    summary = paragraphs[0]
    if len(summary) > max_chars:
        summary = summary[:max_chars].rstrip() + "..."
    return summary


def extract_missing_info(body: str) -> str:
    for heading in (
        "### Información no cubierta y sugerencias de búsqueda",
        "## Información no cubierta y sugerencias de búsqueda",
        "### Informacion no cubierta y sugerencias de busqueda",
        "## Informacion no cubierta y sugerencias de busqueda",
    ):
        idx = body.find(heading)
        if idx != -1:
            return body[idx:].strip()
    return ""


def extract_selected_refs(body: str) -> list[str]:
    refs: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            refs.append(stripped)
    return refs


def collect_source_mentions(text: str) -> list[str]:
    seen: list[str] = []
    for match in re.finditer(r"\[\[Notes/NotebookLM/[^\]]+/Sources/([^\]#|]+)", text):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    for match in re.finditer(r"\[\[Research/Papers/([^\]#|]+)", text):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def split_sections(body: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^(##+)\s+(.+)$", body, re.MULTILINE))
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        heading = match.group(2).strip()
        norm_heading = normalize_heading(heading)
        if norm_heading in SKIP_HEADINGS:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        if content:
            sections.append((heading, content))
    return sections


def summarize_qa_note(vault_note: str) -> dict:
    path = VAULT / vault_note
    content = path.read_text(encoding="utf-8")
    body = cut_before_aux_sections(strip_frontmatter(content).strip())
    return {
        "note": vault_note,
        "summary": extract_summary_paragraph(body),
        "refs": extract_selected_refs(body),
        "sections": split_sections(body),
        "gaps": extract_missing_info(body),
        "sources": collect_source_mentions(body),
    }


def build_crosscutting_sections(qa_data: list[dict]) -> list[str]:
    heading_counter: Counter[str] = Counter()
    sections_by_heading: dict[str, list[str]] = {}
    display_names: dict[str, str] = {}

    for item in qa_data:
        for heading, content in item["sections"]:
            norm_heading = normalize_heading(heading)
            heading_counter[norm_heading] += 1
            display_names.setdefault(norm_heading, heading)
            sections_by_heading.setdefault(norm_heading, []).append(
                f"### Desde [[{item['note']}]]\n\n{content}"
            )

    blocks: list[str] = []
    for norm_heading, count in heading_counter.most_common():
        if count < 2:
            continue
        blocks.append(
            f"## {display_names[norm_heading]}\n\n"
            + "\n\n".join(sections_by_heading[norm_heading])
        )
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile QA notes into a block summary note")
    parser.add_argument("--slug", required=True, help="Notebook slug")
    parser.add_argument("--title", required=True, help="Block summary title")
    parser.add_argument("--dashboard", required=True, help="Dashboard title")
    parser.add_argument("--qa-note", nargs="+", required=True, help="Vault-relative QA notes")
    parser.add_argument("--date", default=None, help="Date for note")
    args = parser.parse_args()

    note_date = args.date or date.today().isoformat()
    qa_data = [summarize_qa_note(note) for note in args.qa_note]

    all_refs: list[str] = []
    for item in qa_data:
        for ref in item["refs"]:
            if ref not in all_refs:
                all_refs.append(ref)

    all_sources: list[str] = []
    for item in qa_data:
        for source in item["sources"]:
            if source not in all_sources:
                all_sources.append(source)

    crosscutting_sections = build_crosscutting_sections(qa_data)
    per_qa_blocks = []
    for item in qa_data:
        summary = item["summary"] or "_Sin resumen extractivo disponible_"
        per_qa_blocks.append(
            "\n".join(
                [
                    f"## [[{item['note']}]]",
                    "",
                    summary,
                ]
            )
        )

    gaps = [item["gaps"] for item in qa_data if item["gaps"]]
    gaps_block = "\n\n".join(gaps) if gaps else "- No se detectaron gaps explícitos en las QA exportadas."
    refs_block = "\n".join(f"- {ref}" for ref in all_refs) if all_refs else "- Sin referencias consolidadas"
    sources_block = (
        "\n".join(f"- [[Notes/NotebookLM/{args.slug}/Sources/{src}|{src}]]" for src in all_sources)
        if all_sources
        else "- Sin fuentes detectadas"
    )
    qa_block = "\n".join(f"- [[{item['note']}]]" for item in qa_data)
    thesis_bullets = "\n".join(
        f"- {item['summary']}" for item in qa_data if item["summary"]
    ) or "- Las QA exportadas requieren revisión manual para extraer una tesis central más nítida."

    dashboard_path = f"Notes/Dashboards/{args.dashboard}"
    output_rel = f"Notes/NotebookLM/{args.slug}/QA/summaries/{note_date} {args.title}.md"
    content = f"""---
type: block-summary
status: current
date: {note_date}
source: "notebooklm:{args.slug}:block-summary"
related:
  - "[[{dashboard_path}]]"
---

# {args.title}

Resumen sintético y reutilizable para escritura, compilado a partir de QA exportadas del notebook.

## QA fuente

{qa_block}

## Referencias bibliográficas clave del bloque

{refs_block}

## Fuentes núcleo del bloque

{sources_block}

## Hilo central del bloque

{thesis_bullets}

## Resumen por QA

{chr(10).join(per_qa_blocks)}
"""

    if crosscutting_sections:
        content += "\n## Ejes transversales detectados\n\n" + "\n\n".join(crosscutting_sections) + "\n"

    content += f"""
## Gaps y puntos a reforzar

{gaps_block}
"""

    output = VAULT / output_rel
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(output_rel)


if __name__ == "__main__":
    main()
