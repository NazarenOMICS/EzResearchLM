# Operación legacy con wrappers PowerShell

Solo para corridas creadas antes de EZ v2 y operadas con sus wrappers originales.
Para investigaciones nuevas, seguir `docs/ez-host-operator.md`. La referencia de
comandos está en `docs/legacy-reference.md`.

## Guía del agente (antes en CLAUDE.md)

The remainder is a **legacy compatibility reference only**, for existing runs
without an EZ contract. It does not replace the host guide for new research.

Legacy operator responsibilities:

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

## /research

The workflow below is **legacy reference only** for an explicitly selected old
wrapper run. Its global must-have gate is not the policy model of EZ v2.

Operate one EZresearchLM evidence run.

Input expected from the user:

- research question;
- project name;
- slug;
- must-have papers, if any.

Workflow:

1. Run setup readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

2. Convert the research question into 6-10 focused academic search queries.
3. Write a JSON array of strings to:
   `runs\<project>\<slug>\queries-<slug>.json`
4. Write a must-have JSON file if required sources are named:
   `runs\<project>\<slug>\must-have-<slug>.json`
5. Show both files to the user.
6. Run `scripts\run_hermes_pipeline.ps1` with:
   - `-Project`;
   - `-Slug`;
   - `-Goal`;
   - `-QueriesFile`;
   - `-MustHaveFile` when available;
   - `-StopIfMissingMustHave`.
7. If the pipeline returns `NEEDS_SOURCE_RESCUE`, stop and run the doctor.
8. If the pipeline returns `NEEDS_QUESTIONS`, prepare focused NotebookLM
   questions with integer IDs, then resume with `-FromExistingQuestions`.
9. Use only exported NotebookLM summaries and citation audits for claims.

Never answer the literature question from model memory.

## /setup

The steps below are **legacy reference only** for an explicitly selected old
wrapper workflow. They do not apply to normal EZ onboarding.

Help the user configure EZresearchLM.

Steps:

1. Read `README.md`, `SETUP.md`, and `CLAUDE.md`.
2. Check whether `.env` exists.
3. If `.env` is missing, suggest copying `.env.example`.
4. Ask where the user wants outputs saved:
   - run state and logs: `EZRESEARCH_RUNS_ROOT`
   - search metadata and PDFs: `EZRESEARCH_SEARCH_ROOT`
   - imported notes/vault: `EZRESEARCH_VAULT`
5. For a new clone, run the setup checker and installer:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -Install
```

This creates `.venv`, installs the local package, creates `.env` if needed, and
persists `EZRESEARCH_PYTHON=.venv\Scripts\python.exe`.

6. If dependencies are already installed, run only the checker:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

7. If the user gives custom paths, run for example:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" `
  -InitEnv `
  -Install `
  -RunsRoot "D:\ezresearch-runs" `
  -SearchRoot "E:\ezresearch-paper-cache" `
  -Vault "D:\ezresearch-vault"
```

8. If NotebookLM auth fails, run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
```

9. Run the checker again and report readiness.
10. Do not start a real research run until the user has a question, query file,
   and optional must-have file.

Output a short setup checklist, detected paths, missing dependencies, and exact
next commands.

## /doctor

The commands below are **legacy reference only**, when operating a run with its
original wrappers. Do not ask for project/slug again if its path is already known.

Diagnose an EZresearchLM run.

Ask the user for:

- `Project`
- `Slug`

Then run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "<project>" `
  -Slug "<slug>"
```

Report:

- run stage/status;
- candidate count;
- downloaded PDFs;
- missing must-have sources;
- NotebookLM notebook id;
- QA/citation audit state;
- exact resume command.

Do not manually hunt sources unless the user explicitly asks.
