# EZresearchLM

## EZ refactor: internal candidate

The new interface is `ez`, operated by one agent named **EZ**. Your existing host
agent prepares the research plan and reviews NotebookLM evidence; no additional
model API is required. This refactor is still under validation. Offline tests and
wheel installation do **not** establish launch readiness: authenticated E2E runs,
closed beta and the release gates remain pending.

```powershell
python -m pip install -e .
ez setup --check
ez context --project my-project
ez research "My research question" --project my-project --plan-only
ez status <run-id>
ez doctor <run-id>
ez rescue <run-id>
ez continue <run-id>
```

Read [the EZ host workflow](docs/ez-host-operator.md) for planning, scoped source
policies, PDF rescue, reviewed claims and partial answers. `ez setup` initializes
local configuration without replacing it; `--install-notebooklm` installs the
supported NotebookLM CLI in an isolated environment. The user completes login.
QMD remains optional.

For legacy runs, `ez doctor <path> --migration-preview --json` produces a reviewed
snapshot; `--migrate <preview-hash>` creates a separate EZ run without overwriting
the originals. Source identity and old notebook mappings still require review.
Details and release criteria are in the
[implementation plan](docs/ez-refurbish-implementation-plan.md).

The sections below document the historical wrappers retained during migration.
For new EZ runs, use the workflow above. Legacy planner integrations are optional
dependencies (`pip install '.[legacy-planners]'`), not part of the host-agent backend.

NotebookLM-centered research automation for Claude Code, Codex, Hermes, or any
local agent that can run shell commands.

EZresearchLM turns literature search into a traceable evidence pipeline:
discover papers, resolve identifiers, acquire PDFs, rescue missing required
sources, upload documents to NotebookLM, ask focused questions, export cited
answers, and keep enough state to debug or resume the run.

The core rule is simple: the operator orchestrates, but NotebookLM is the
evidence engine. Claude Code, Codex, Hermes, or another agent can plan queries,
run wrappers, inspect logs, and synthesize cited outputs. Strong academic
claims should come from NotebookLM answers over imported sources, not from
model memory.

## What This Is

EZresearchLM is the shared pipeline. Claude Code, Codex, and Hermes are
compatible operator interfaces over that same pipeline.

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

It is operator-agnostic at the orchestration layer:

- Claude Code is a polished user-facing operator for setup and research runs.
- Codex works well for implementation, smoke testing, debugging, and repo
  maintenance.
- Hermes is the historical research operator/orchestrator name for this workflow.
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
- Anna fallback requires a source-specific consent receipt; no browser challenge automation.
- Optional: Unpaywall and NCBI email/API settings for better acquisition.

## Agent-First Quick Start

Most users should operate EZresearchLM through an agent instead of typing every
PowerShell command manually. The agent is the interface; EZresearchLM is the
pipeline; NotebookLM is the evidence engine.

### Claude Code

Open the repo in Claude Code:

```powershell
claude
```

Then run:

```text
/setup
```

Recommended prompt:

```text
Use this repository as EZresearchLM. Read CLAUDE.md and README.md, configure the
project, create query and must-have JSON files for my research question, and run
only the official wrappers. Do not answer bibliographic claims from memory.
```

Claude-specific guide: `docs/claude-operator-guide.md`.

### Codex

Open the repo in Codex and use:

```text
Use this repository as EZresearchLM. Read AGENTS.md and README.md, run the smoke
tests, then help me create query and must-have JSON files. Use only the official
PowerShell wrappers for research runs. Do not answer from memory.
```

Codex-specific guide: `docs/codex-operator-guide.md`.

### Hermes

Hermes is the historical research operator/orchestrator for this workflow. Use
the same wrappers and stop states documented here:

```text
NEEDS_SOURCE_RESCUE
NEEDS_QUESTIONS
NEEDS_MORE_QA
NEEDS_CORPUS
```

Hermes should be treated as an operator over EZresearchLM, not as a separate
evidence engine.

### What Agents Should Do

1. Run setup and smoke checks.
2. Ask where outputs should be saved.
3. Create `queries-*.json` as a simple JSON array of strings.
4. Create `must-have-*.json` when specific papers are required.
5. Run `run_hermes_pipeline.ps1`.
6. Stop at `NEEDS_SOURCE_RESCUE` if required sources are missing.
7. Create NotebookLM questions only after sources are ready.
8. Read summaries, source curation, and citation audits for final claims.

### First Validation Command

Ask the agent to run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_smoke_tests.ps1" -SkipNetwork -IncludeClaude
```

For a full preflight after NotebookLM auth:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_smoke_tests.ps1" -IncludeClaude -IncludeFullPipelinePreflight
```

## Manual Setup

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

## Detailed Claude Code Workflow

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

## Detailed Codex Workflow

Open the repo in Codex and ask it to read `AGENTS.md`. Codex should use the same
PowerShell wrappers as Claude and Hermes; it should not answer academic claims
from memory.

Recommended first prompt:

```text
Use this repository as EZresearchLM. Read AGENTS.md and README.md, verify setup
with the smoke runner, then help me create queries and must-have files. Use only
the official PowerShell wrappers for research runs.
```

Codex is especially useful for:

1. Auditing and editing the repo.
2. Running smoke tests and interpreting failures.
3. Improving wrappers, docs, and tests.
4. Creating or reviewing query and must-have JSON files.
5. Operating the pipeline when NotebookLM/QMD auth is already configured.

Codex should still preserve the evidence contract:

- NotebookLM remains the evidence engine.
- QMD is recall/index only.
- `source-rescue.json` is the source of truth for missing papers.
- `NEEDS_SOURCE_REVIEW`, `NEEDS_SOURCE_RESCUE`, `NEEDS_CORPUS`, and `NEEDS_MORE_QA` are valid stop
  states.

For the detailed Codex operator contract, see `docs/codex-operator-guide.md`.

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

Review candidates before acquisition:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "membrane-stress" `
  -Project "my-project" `
  -Goal "Build a cited evidence set about membrane stress response" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "Membrane stress evidence" `
  -Dashboard "Membrane stress evidence" `
  -ReviewBeforeAcquisition
```

This stops with `NEEDS_SOURCE_REVIEW` and writes `download-plan.md` in the run
 directory. The plan separates bibliographic priority from full-text access. A
 high-priority paywalled paper should be obtained through institutional,
 repository, or author access and placed in the papers directory before
 resuming acquisition or using `-SkipSearch`.

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
|   |-- codex-operator-guide.md
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

Anna is off by default. In EZ, an explicit source-specific decision uses
`ez rescue <run> --source <id> --allow-anna --anna-url <HTTPS-md5-page>`.
The receipt expires after 24 hours and never authorizes bypassing access controls.
The legacy `-AllowAnnaFallback` or config flag alone is insufficient: the adapter
also requires `EZRESEARCH_ANNA_CONSENT_FILE` for the exact source. Historical
permissions are not silently renewed during migration.

```text
PAPER_SEARCH_MCP_ANNA_TIMEOUT_SECONDS=120
EZRESEARCH_ANNA_CONSENT_FILE=C:\Path\To\source-consent.json
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

In new legacy-wrapper runs, `-StopIfMissingMustHave` controls whether a missing
must-have stops QA. Omission on continuation inherits the effective prior setting;
pre-v2 runs retain their historical gate. EZ uses five policies scoped to the
relevant subquestions and can deliver a reviewed partial answer.

## Safety Model

- NotebookLM is the evidence engine.
- Claude Code, Codex, Hermes, and GPT-style agents are operators.
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
