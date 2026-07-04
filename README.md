# EZresearchLM

NotebookLM-centered research automation for Claude Code, Codex, or any local
agent that can run shell commands.

EZresearchLM turns literature search into a traceable evidence pipeline:
discover papers, resolve identifiers, acquire PDFs, rescue missing required
sources, upload documents to NotebookLM, ask focused questions, export cited
answers, and keep enough state to debug or resume the run.

The core rule is simple: the agent orchestrates, but NotebookLM is the evidence
engine. Claude, Codex, or GPT can plan queries, run wrappers, inspect logs, and
synthesize cited outputs. Strong academic claims should come from NotebookLM
answers over imported sources, not from model memory.

## What This Is

EZresearchLM is a structured workflow that turns Claude Code into a research
operator.

```text
/setup or manual config
        |
        v
create queries + must-have sources
        |
        v
discover -> resolve -> acquire -> source rescue
        |
        v
NotebookLM upload -> focused QA -> citation audit
        |
        v
local notes + QMD recall for future questions
```

It is model-agnostic at the orchestration layer:

- Claude Code is the recommended user-facing agent.
- Codex works well for implementation, debugging, and repo maintenance.
- Other agents can use the same wrappers if they respect the evidence contract.

It is not a local RAG replacement for NotebookLM. QMD/local search is used to
find already processed evidence; it does not create uncited claims.

## What It Does

- Searches PubMed, EuropePMC, OpenAlex, Semantic Scholar, and Crossref.
- Normalizes DOI, PMID, PMCID, title, year, journal, and authors.
- Deduplicates candidate records.
- Downloads open PDFs when available.
- Optionally tries Anna's Archive only after open-access routes fail.
- Validates PDF downloads and records acquisition provenance.
- Writes `source-rescue.json` for missing or failed required sources.
- Stops before NotebookLM QA if required sources are missing.
- Uploads acquired PDFs to NotebookLM.
- Exports NotebookLM answers, summaries, source curation, and citation audits.
- Keeps `run-state.json` so interrupted runs can be diagnosed and resumed.

## Prerequisites

- Windows PowerShell 5.1+ or PowerShell 7.
- Python 3.10+.
- Claude Code, Codex, or another local agent.
- NotebookLM account and browser auth.
- `notebooklm` CLI available in PATH.
- QMD installed if you want local recall over exported notes.
- Optional: Playwright/Chromium for Anna fallback.
- Optional: Unpaywall and NCBI email/API settings for better acquisition.

## Quick Start

### 1. Clone

```powershell
git clone https://github.com/NazarenOMICS/EzResearchLM.git
cd EzResearchLM
```

### 2. Install And Create `.env`

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -Install
```

This creates `.venv`, installs EZresearchLM in editable mode, creates `.env` if
needed, and sets `EZRESEARCH_PYTHON=.venv\Scripts\python.exe`.

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
```

### 3. Configure Output Paths And Optional Keys

```powershell
notepad .env
```

Minimal `.env`:

```text
EZRESEARCH_PYTHON=.venv\Scripts\python.exe
PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=you@example.com
NCBI_EMAIL=you@example.com
```

Choose where results are saved:

```text
EZRESEARCH_RUNS_ROOT=D:\ezresearch-runs
EZRESEARCH_SEARCH_ROOT=E:\ezresearch-paper-cache
EZRESEARCH_VAULT=D:\ezresearch-vault
```

Defaults are local folders inside the repository:

- `runs/`: run state, questions, status, rescue queues.
- `Search/`: search metadata and acquired PDFs.
- `Notes/`: imported NotebookLM notes.
- `Research/Papers/`: mirrored paper files.

You can also choose a search output directory per run with `-SaveDir`.

### 4. Authenticate NotebookLM

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
notebooklm list
```

### 5. Verify Setup

Search/acquisition readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

Claude Code readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -CheckClaude
```

If the workspace trust dialog blocks non-interactive Claude tests, either open
Claude Code in this repo once and accept trust, or run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -TrustClaudeWorkspace
```

Full NotebookLM QA readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

### 6. Run A Source Pipeline

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "example-topic" `
  -Project "general" `
  -Goal "Build an evidence set for an example academic question" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "EZresearchLM example" `
  -Dashboard "EZresearchLM example dashboard" `
  -MustHaveFile ".\examples\must-have.example.json" `
  -StopIfMissingMustHave
```

If required sources are missing, the pipeline stops before NotebookLM QA:

```text
NEEDS_SOURCE_RESCUE
```

Run the doctor:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "general" `
  -Slug "example-topic"
```

## Claude Code Workflow

Open the repo in Claude Code:

```powershell
claude
```

If `claude` is not in PATH, run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -CheckClaude
```

The checker reports the detected `claude.exe` path and whether Claude is logged
in and trusted for this workspace.

Use the included command prompts:

```text
/setup
/research
/doctor
```

Recommended first prompt:

```text
Use this repository as a NotebookLM-centered research pipeline. Read CLAUDE.md,
help me configure .env, create a queries JSON array and must-have file for my
question, then run the official PowerShell wrappers only.
```

Claude should act as the operator:

1. Clarify the research question.
2. Write `examples`-style query and must-have JSON files.
3. Run `setup_ezresearch.ps1 -RequireFullPipeline` before full QA.
4. Run `run_hermes_pipeline.ps1`.
5. Stop at `NEEDS_SOURCE_RESCUE` if required sources are missing.
6. Generate focused NotebookLM questions only after sources are ready.
7. Read summaries and citation audits, not raw giant exports.

For the detailed Claude operator contract, see
`docs/claude-operator-guide.md`.

## Core Commands

Search/acquire only:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_search_topic.ps1" `
  -Slug "membrane-stress" `
  -QueriesFile ".\examples\queries.example.json" `
  -MustHaveFile ".\examples\must-have.example.json" `
  -SaveDir "E:\paper-cache\membrane-stress" `
  -AllowAnnaFallback
```

Full pipeline:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "membrane-stress" `
  -Project "my-project" `
  -Goal "Build a cited evidence set about membrane stress response" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "Membrane stress evidence" `
  -Dashboard "Membrane stress evidence" `
  -MustHaveFile ".\examples\must-have.example.json" `
  -AllowAnnaFallback `
  -StopIfMissingMustHave
```

Resume after questions are prepared:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "membrane-stress" `
  -Project "my-project" `
  -Goal "Build a cited evidence set about membrane stress response" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "Membrane stress evidence" `
  -Dashboard "Membrane stress evidence" `
  -SkipSearch `
  -FromExistingQuestions `
  -ExistingNotebookId "<notebook-id>"
```

Diagnose a run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "my-project" `
  -Slug "membrane-stress"
```

## File Structure

```text
EZresearchLM/
|-- README.md
|-- SETUP.md
|-- CLAUDE.md
|-- AGENTS.md
|-- .env.example
|-- examples/
|   |-- queries.example.json
|   |-- must-have.example.json
|   `-- questions.example.json
|-- scripts/
|   |-- setup_ezresearch.ps1
|   |-- run_hermes_pipeline.ps1
|   |-- run_hermes_answer.ps1
|   |-- run_hermes_doctor.ps1
|   |-- run_search_topic.ps1
|   |-- upload_sources_parallel.ps1
|   `-- auto_login.ps1
|-- packages/
|   `-- paper_search/
|       |-- search_topic.py
|       |-- run_search_topic_wrapper.py
|       |-- paper_search_mcp/
|       `-- tests/
|-- notebooklm/
|   `-- scripts/
|-- docs/
|   |-- claude-operator-guide.md
|   |-- configuration.md
|   |-- debugging.md
|   |-- pipeline-reference.md
|   `-- source-rescue.md
|-- runs/
|-- Search/
|-- Notes/
`-- Research/Papers/
```

## How The Pipeline Works

1. `discover`: query scholarly sources and collect candidate records.
2. `resolve`: normalize identifiers and confidence fields.
3. `acquire`: try direct/OA routes first.
4. `fallback`: optionally try Anna's Archive only after OA routes fail.
5. `rescue`: keep missing or failed required sources visible.
6. `notebook`: upload acquired PDFs to NotebookLM.
7. `qa`: ask focused NotebookLM questions.
8. `audit`: export summaries and citation checks.

The acquisition layer writes artifacts incrementally. If a download, Anna
lookup, or browser step hangs, the run should still leave enough state for
`run_hermes_doctor.ps1` to report what happened.

## Customization

### Change Output Locations

Use `.env`:

```text
EZRESEARCH_RUNS_ROOT=D:\research-runs
EZRESEARCH_SEARCH_ROOT=E:\paper-cache
EZRESEARCH_VAULT=D:\research-vault
```

Or set them from setup:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" `
  -InitEnv `
  -RunsRoot "D:\research-runs" `
  -SearchRoot "E:\paper-cache" `
  -Vault "D:\research-vault"
```

Or override one search:

```powershell
-SaveDir "E:\paper-cache\custom-topic"
```

### Change Sources

```powershell
-Sources "pubmed,europepmc,openalex"
```

### Control Anna Fallback

Anna is off unless `-AllowAnnaFallback` is passed or the must-have config sets
`allow_anna_fallback: true`.

```text
PAPER_SEARCH_MCP_ANNA_TIMEOUT_SECONDS=120
PAPER_SEARCH_MCP_PLAYWRIGHT_CHROMIUM=C:\Path\To\chrome.exe
```

### Must-Have Sources

Use `must-have` files when a paper is required for the question:

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

If a must-have source is missing, the pipeline stops before QA.

## Safety Model

- NotebookLM is the evidence engine.
- Claude/Codex/GPT are orchestration agents.
- QMD is recall/index only.
- Anna's Archive is acquisition fallback only.
- Missing sources remain `manual_needed`; they are not silently converted into
  claims.
- Real PDFs, run artifacts, cookies, tokens, and `.env` are ignored by Git.

## Validation

Full smoke suite:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_smoke_tests.ps1" `
  -IncludeClaude `
  -IncludeFullPipelinePreflight
```

Use `-SkipNetwork` for an offline-only smoke pass.

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -SkipNotebookLM -SkipQmd
$env:PYTHONPATH = "$PWD\packages\paper_search"
python -m py_compile .\packages\paper_search\search_topic.py .\packages\paper_search\run_search_topic_wrapper.py
python -m unittest discover -s .\packages\paper_search\tests
```

PowerShell parse check:

```powershell
$files = Get-ChildItem .\scripts -Filter *.ps1
foreach ($file in $files) {
  $errs = $null
  $null = [System.Management.Automation.PSParser]::Tokenize(
    (Get-Content -LiteralPath $file.FullName -Raw),
    [ref]$errs
  )
  if ($errs.Count -gt 0) { throw $file.FullName }
}
```

## Limits

- NotebookLM auth is external and can expire.
- Some publishers block automated PDF acquisition.
- Anna fallback is best-effort and provenance-marked.
- The repo ships no real corpus, PDFs, NotebookLM exports, or credentials.
- The current interface is CLI/agent-first, not a graphical app.

## License

MIT.
