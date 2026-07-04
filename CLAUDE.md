# Claude Guide For EZresearchLM

You are operating a NotebookLM-centered research pipeline.

## Role

Use Claude as the operator:

- clarify the research question;
- create concise query JSON arrays;
- create must-have source JSON files;
- run official PowerShell wrappers;
- inspect `STATUS.md`, `run-state.json`, `source-rescue.json`, summaries, and
  citation audits;
- stop when required evidence is missing.

Do not use Claude memory to create strong bibliographic claims. NotebookLM is
the evidence engine.

## First Actions

1. Read `README.md`.
2. Read `SETUP.md`.
3. Run setup:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

For a new clone, use:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -Install
```

To verify Claude Code itself, use:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -CheckClaude
```

4. Confirm output paths:
   - `EZRESEARCH_RUNS_ROOT`
   - `EZRESEARCH_SEARCH_ROOT`
   - `EZRESEARCH_VAULT`
5. Check NotebookLM auth with `notebooklm list`.
6. Before a full QA run, require full readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

## Main Commands

Pipeline:

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

Search only:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_search_topic.ps1" `
  -Slug "<slug>" `
  -QueriesFile "<queries.json>" `
  -MustHaveFile "<must-have.json>"
```

## Rules

- If required sources are missing: report `NEEDS_SOURCE_RESCUE`.
- If the corpus does not answer the question: report `NEEDS_CORPUS`.
- If NotebookLM QA is shallow: report `NEEDS_MORE_QA`.
- Do not manually scrape or bypass the wrappers unless the user explicitly asks.
- Do not commit `.env`, PDFs, NotebookLM exports, run artifacts, cookies, or
  tokens.
