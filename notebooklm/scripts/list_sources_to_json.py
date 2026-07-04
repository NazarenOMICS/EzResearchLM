"""Export NotebookLM sources to the JSON shape expected by Hermes.

The notebooklm-py 0.7.x public CLI already emits the source list JSON Hermes
needs. Use that instead of importing private notebooklm internals, whose names
change across notebooklm-py releases.
"""
import argparse
import json
import subprocess
import sys


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def main(notebook_id: str, title: str, out_path: str) -> int:
    cmd = [
        sys.executable,
        "-m",
        "notebooklm",
        "source",
        "list",
        "--notebook",
        notebook_id,
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.stderr.write(proc.stdout)
        return proc.returncode

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Could not parse notebooklm source list JSON: {exc}\n")
        sys.stderr.write(proc.stdout)
        return 1

    result.setdefault("notebook_id", notebook_id)
    if title:
        result["notebook_title"] = title
    sources = result.get("sources") or []
    result["sources"] = sources
    result["count"] = len(sources)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"SAVED: {out_path} ({len(sources)} sources)")
    return 0


ap = argparse.ArgumentParser(description="Dump NotebookLM source list to JSON")
ap.add_argument("--notebook", required=True, help="Notebook UUID")
ap.add_argument("--out", required=True, help="Output JSON path")
ap.add_argument("--title", default="", help="Notebook title label")
args = ap.parse_args()
raise SystemExit(main(args.notebook, args.title, args.out))
