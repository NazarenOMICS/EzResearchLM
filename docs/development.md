# Developing EZresearchLM

For agents and people changing EZ's code or documentation. To operate EZ for a person, read
`AGENTS.md` instead.

## Rules

1. Never invent data, references or results. If something cannot be verified (for example,
   the network blocks PubMed or OpenAlex), say so; do not simulate it.
2. Do not commit `.env`, PDFs, NotebookLM exports, run folders, cookies or tokens; do not read
   or copy cookies. Anna's Archive and Sci-Hub are not supported; never automate access
   challenges.
3. Every behaviour change carries its test; every flow change, its update in
   `docs/ez-host-operator.md` or `docs/agent/` and a dated entry in `docs/roadmap.md`.
4. The gold set (`gold_set_benchmark/`) is for scoring only (`puntuar.py`). Agent-facing text
   (`AGENTS.md`, `CLAUDE.md`, `docs/ez-host-operator.md`, `docs/agent/`, `ez setup`'s
   introduction) never names its topics or authors; a test checks it.
5. Do not rewrite git history without explicit permission.

## Validation

Before committing:

```powershell
python scripts/validate.py
python -m pip install -e ".[dev]"
python -m pyflakes packages/ez tests scripts
```

If packaging changes, install the wheel outside the checkout and run
`python -I scripts/check_installed.py` with that environment's Python.

## File integrity

Before committing edits to long-lived Markdown or index files:

1. Re-read the complete edited file with the agent's file-read tool when one is available. Do
   not rely only on shell views such as `cat`, `tail` or `wc`: a sandboxed shell can show
   stale or truncated content.
2. Confirm the file ends at the expected final section or sentence.
3. Review `git diff --stat` and the full `git diff` before staging. Unexpected large deletions
   or mid-word endings are blockers.

## Repository layout

| Resource | Path |
|---|---|
| EZ package | `packages/ez/` |
| Literature search providers | `packages/paper_search/` |
| Agent guide (core and sections) | `docs/ez-host-operator.md`, `docs/agent/` |
| User guide | `docs/ez-user-guide.md` |
| Tests | `tests/`, `packages/paper_search/tests/` |
| Claude Desktop extension | `desktop/` |
| Benchmark and gold set | `gold_set_benchmark/` |
| Plan in force | `docs/roadmap.md` |

Runs live outside the repository, in `~/.ezresearch/runs` by default (`EZRESEARCH_RUNS_ROOT`
overrides it). Projects, inboxes and reports are described in `docs/carpetas.md`. Runs created
by the PowerShell wrappers of earlier versions can be inspected with
`ez doctor <path> --migration-preview --json`; apply only the reviewed preview hash.

## Acquisition order

1. direct PDF URL
2. PMC OA PDF or archive
3. Europe PMC and OpenAlex source-native open access
4. Unpaywall
5. CORE, OpenAIRE and repository locations

When every route fails, the source stays `manual_needed`: the person drops the PDF in the
project inbox or imports it with `ez rescue <run> --source <id> --import <pdf>`, and its origin
is recorded.
