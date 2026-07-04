# Claude Operator Guide

EZresearchLM is designed so Claude Code can operate the research pipeline
without becoming the evidence engine.

## Mental Model

- Claude plans and executes.
- NotebookLM reads sources and answers.
- QMD recalls already imported notes.
- `source-rescue.json` records what is missing.

Claude should never fill evidence gaps from memory.

## First Run In Claude Code

Open the repository:

```powershell
cd <repo>
claude
```

Run:

```text
/setup
```

The command should:

1. read `README.md`, `SETUP.md`, and `CLAUDE.md`;
2. run `scripts/setup_ezresearch.ps1 -InitEnv -Install` on a fresh clone;
3. configure output roots if requested;
4. verify Python, NotebookLM, and QMD;
5. stop before research until inputs are clear.

If dependencies are already installed, Claude can run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

Before any run that must reach NotebookLM QA, Claude should require full
readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

## Recommended User Prompt

```text
I want to build an evidence set for this question:
<paste question>

Use EZresearchLM. Create queries and must-have sources, show me the files, then
run the official wrappers. Do not answer from memory.
```

## Output Locations

Claude should ask where the user wants outputs:

- `EZRESEARCH_RUNS_ROOT`: run state and rescue queues.
- `EZRESEARCH_SEARCH_ROOT`: search metadata and acquired PDFs.
- `EZRESEARCH_VAULT`: imported notes and paper mirrors.

If the user does not care, leave defaults.

Claude can set these paths without manually editing `.env`:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" `
  -InitEnv `
  -RunsRoot "D:\ezresearch-runs" `
  -SearchRoot "E:\ezresearch-paper-cache" `
  -Vault "D:\ezresearch-vault"
```

## Safe Stop States

- `NEEDS_SOURCE_RESCUE`: required source missing; run doctor, do not QA.
- `NEEDS_QUESTIONS`: sources ready; create focused NotebookLM questions.
- `NEEDS_MORE_QA`: NotebookLM answer was too shallow.
- `NEEDS_CORPUS`: existing evidence does not cover the question.

## What Claude Can Read

Prefer:

- `STATUS.md`
- `run-state.json`
- `source-rescue.json`
- `missing-sources.md`
- `candidate-sources.json`
- `QA/summaries/*QA Summary.md`
- `*Source Curation.md`
- `*Citation Audit.md`

Avoid reading huge raw exports unless debugging.

## Validation

Before reporting success, Claude should run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -SkipNotebookLM -SkipQmd
python -m unittest discover -s .\packages\paper_search\tests
```

Full pipeline readiness also requires NotebookLM and QMD checks without the skip
flags, preferably with `-RequireFullPipeline`.
