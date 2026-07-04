# EZresearchLM Setup

This guide gets a new user from clone to first recoverable research run.

## 1. Install Prerequisites

Install:

- Python 3.10 or newer.
- Git.
- Claude Code or another local agent.
- `notebooklm` CLI.
- QMD if you want local evidence recall.

Optional:

- Playwright/Chromium for Anna fallback.
- Unpaywall email.
- NCBI email/API key.

## 2. Create Environment

Recommended:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -Install
```

This creates `.venv`, installs EZresearchLM, creates `.env` if needed, and sets
`EZRESEARCH_PYTHON`.

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

## 3. Configure `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Or let the setup checker create/update it:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

Before a full NotebookLM QA run, require full readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

To set custom output locations from the command line:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" `
  -InitEnv `
  -RunsRoot "D:\ezresearch-runs" `
  -SearchRoot "E:\ezresearch-paper-cache" `
  -Vault "D:\ezresearch-vault"
```

Recommended minimum:

```text
EZRESEARCH_PYTHON=.venv\Scripts\python.exe
PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=you@example.com
NCBI_EMAIL=you@example.com
```

Choose output locations:

```text
EZRESEARCH_RUNS_ROOT=D:\ezresearch-runs
EZRESEARCH_SEARCH_ROOT=E:\ezresearch-paper-cache
EZRESEARCH_VAULT=D:\ezresearch-vault
```

If these are blank, EZresearchLM writes to local folders inside the repo.

## 4. Authenticate NotebookLM

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
notebooklm list
```

## 5. Prepare Inputs

Queries file must be a JSON array of strings:

```json
[
  "ethambutol Mycobacterium smegmatis proteomics",
  "Mycobacterium smegmatis ethambutol response PMID 20686769"
]
```

Must-have file:

```json
{
  "must_have": [
    {
      "pmid": "20686769",
      "title": "Comparative proteome analysis of Mycobacterium smegmatis in response to ethambutol"
    }
  ],
  "nice_to_have": [],
  "allow_anna_fallback": false
}
```

## 6. Run Pipeline

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "first-run" `
  -Project "general" `
  -Goal "Build a traceable evidence set for my research question" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "EZresearchLM first run" `
  -Dashboard "EZresearchLM first run" `
  -MustHaveFile ".\examples\must-have.example.json" `
  -StopIfMissingMustHave
```

## 7. If It Stops

`NEEDS_SOURCE_RESCUE` is a safe stop. It means a required source was missing and
NotebookLM QA was not run.

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "general" `
  -Slug "first-run"
```

The doctor prints missing sources, artifacts, and the exact resume command.

## 8. Claude Code Usage

Open Claude Code in the repo and run:

```text
/setup
```

`/setup` should run `scripts/setup_ezresearch.ps1 -InitEnv -Install` for a new
clone, ask where outputs should be saved, verify NotebookLM/QMD, and stop
before any real research run.

Then ask Claude to create query/must-have files and run the wrappers.

Claude should not answer literature questions from memory. It should operate the
pipeline, inspect `source-rescue.json`, and use NotebookLM outputs for cited
answers.

See `docs/claude-operator-guide.md` for the full operator contract.
