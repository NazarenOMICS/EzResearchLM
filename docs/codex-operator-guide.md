# Codex Operator Guide

EZresearchLM can be operated from Codex without changing the pipeline. Codex is
an operator interface, not the evidence engine.

## Mental Model

- EZresearchLM is the pipeline.
- Codex operates, edits, validates, and debugs the pipeline.
- NotebookLM reads imported sources and answers evidence questions.
- QMD recalls already exported notes.
- `source-rescue.json` records missing or failed sources.

Codex should never fill bibliographic gaps from model memory.

## First Run In Codex

Open the repository in Codex and start by reading:

1. `AGENTS.md`
2. `README.md`
3. `SETUP.md`

Then run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -SkipNotebookLM -SkipQmd
```

For a full local validation pass:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_smoke_tests.ps1" -SkipNetwork -IncludeClaude
```

For a network-enabled smoke pass:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_smoke_tests.ps1" -IncludeClaude -IncludeFullPipelinePreflight
```

## Recommended User Prompt

```text
Use EZresearchLM as a NotebookLM-centered research pipeline. Read AGENTS.md and
README.md, verify setup, create query and must-have JSON files for this research
question, and run only the official PowerShell wrappers. Do not answer from
memory.
```

## What Codex Is Best For

- Repo audits and implementation fixes.
- Smoke testing and debugging wrapper failures.
- Maintaining docs and public delivery quality.
- Creating structured query and must-have files.
- Reading `run-state.json`, `source-rescue.json`, `STATUS.md`, summaries, and
  citation audits.
- Explaining what failed and which exact command resumes the run.

## What Codex Should Not Do

- Replace NotebookLM QA with local model memory.
- Invent citations, mechanisms, numeric claims, or source conclusions.
- Read huge raw source exports by default.
- Manually scrape papers unless the user explicitly requests manual search.
- Hide a missing must-have source by calling it absent from the literature.

## Research Run Pattern

1. Clarify the research question.
2. Create `queries-*.json` as a simple JSON array of strings.
3. Create `must-have-*.json` when named required sources exist.
4. Run setup/preflight.
5. Run `run_hermes_pipeline.ps1`.
6. Stop at `NEEDS_SOURCE_RESCUE` and run doctor.
7. If `NEEDS_QUESTIONS`, create focused NotebookLM questions with integer IDs.
8. Resume with `-SkipSearch -FromExistingQuestions -ExistingNotebookId`.
9. Use exported NotebookLM summaries and citation audits for final claims.

## Safe Commands

Setup:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

Full readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

Search/acquire only:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_search_topic.ps1" `
  -Slug "<slug>" `
  -QueriesFile "<queries.json>" `
  -MustHaveFile "<must-have.json>"
```

Full pipeline:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "<slug>" `
  -Project "<project>" `
  -Goal "<goal>" `
  -QueriesFile "<queries.json>" `
  -NotebookTitle "<NotebookLM title>" `
  -Dashboard "<dashboard title>" `
  -MustHaveFile "<must-have.json>" `
  -StopIfMissingMustHave
```

Doctor:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "<project>" `
  -Slug "<slug>"
```

## Stop States

- `NEEDS_SOURCE_RESCUE`: required source missing; do not QA.
- `NEEDS_QUESTIONS`: sources ready; create NotebookLM question file.
- `NEEDS_MORE_QA`: NotebookLM answer is too shallow.
- `NEEDS_CORPUS`: current evidence does not cover the question.

## Reporting

When reporting to the user, Codex should include:

- what command ran;
- what stage passed or failed;
- where artifacts were written;
- whether NotebookLM/QMD/Claude auth is required;
- the exact next command.
