# EZresearchLM Agent Guide

EZresearchLM is a NotebookLM-centered evidence pipeline for academic research.
It discovers papers, acquires PDFs, builds a traceable source set, asks
NotebookLM focused questions, exports cited answers, and keeps enough run state
to debug or resume interrupted work.

## Operator Model

EZ is the single user-facing operator. Claude Code, Codex, Hermes, or another
host agent supplies its planning and synthesis without an additional model API.
Read `docs/ez-host-operator.md` before operating the new `ez` interface. The host
prepares contracts and QA reviews on the user's behalf; do not ask users to edit
JSON. The historical wrappers remain available for existing runs.

NotebookLM remains the evidence engine. The current implementation is an internal
candidate; authenticated E2E and closed beta are still required before release.

## Core Rules

- NotebookLM is the evidence and QA engine.
- Local search and QMD are recall/acquisition helpers, not answer engines.
- Do not write strong bibliographic claims from memory.
- Before drafting academic prose in Nazareno's voice, read `Rules_Of_Writing.md` completely. Its EZresearchLM-specific section preserves QA citation markers, evidence gaps, and `NEEDS_*` states during intermediate synthesis.
- If evidence is missing, emit `NEEDS_CORPUS`, `NEEDS_MORE_QA`,
  `NEEDS_SOURCE_REVIEW`, or `NEEDS_SOURCE_RESCUE`.
- Anna's Archive is an optional acquisition fallback only. It must never answer
  questions or erase provenance. Require source-scoped consent; never automate
  access challenges or integrate Sci-Hub.
- Do not commit real PDFs, notebooks, tokens, cookies, source exports, or run
  artifacts.

## File Integrity Checks

Before committing edits to long-lived Markdown or index files:

- Re-read the complete edited file with the agent's file-read tool when one is
  available. Do not rely only on shell views such as `cat`, `tail`, or `wc`,
  because a sandboxed shell can show stale or truncated content.
- Confirm the file ends at the expected final section or sentence.
- Review `git diff --stat` and the full `git diff` for the edited file before
  staging. Unexpected large deletions or mid-word endings are blockers.

## Repository Layout

| Resource | Path |
|---|---|
| Project root | repository root |
| Main wrappers | `scripts/` |
| Paper search package | `packages/paper_search/` |
| NotebookLM helper scripts | `notebooklm/scripts/` |
| Run artifacts | `runs/` |
| Search/PDF artifacts | `Search/` |
| NotebookLM notes | `Notes/` |
| Mirrored PDFs | `Research/Papers/` |

All wrappers resolve paths from their own repository root. Override paths with
environment variables or `.env`.

Important output overrides:

- `EZRESEARCH_RUNS_ROOT`: run state, logs, questions, rescue queues.
- `EZRESEARCH_SEARCH_ROOT`: search metadata and acquired PDFs.
- `EZRESEARCH_VAULT`: imported notes and mirrored paper files.

## Main Commands

New EZ runs use `ez setup`, `ez context`, `ez research`, `ez continue`, `ez status`,
`ez doctor` and `ez rescue`. See `docs/ez-host-operator.md` for the host workflow.
Use `ez doctor <legacy-path> --migration-preview --json` to inspect a sidecar
migration; apply only the reviewed preview hash. Original files are preserved.

The following commands are the compatibility interface for historical runs.

Create or extend a source set:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "<slug>" `
  -Project "<project>" `
  -Goal "<goal>" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "<NotebookLM title>" `
  -Dashboard "<dashboard title>"
```

Run a question over existing evidence:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_answer.ps1" `
  -Question "<question>" `
  -Mode answer
```

Diagnose a failed or interrupted run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "<project>" `
  -Slug "<slug>"
```

## Source Rescue

Each run can produce:

- `candidate-sources.json`
- `source-rescue.json`
- `missing-sources.md`
- `download-plan.md` when `-ReviewBeforeAcquisition` is used
- `run-state.json`

The legacy pipeline stops before QA when required sources are missing and
`-StopIfMissingMustHave` is effective. New runs default to reporting the gap;
explicit true blocks and explicit false does not. Continuing inherits the last
effective decision; pre-v2 runs preserve their historical blocking behavior.
EZ policies withhold only their affected scopes and distinguish partial answers.
The compatible source-rescue signal is:

```text
NEEDS_SOURCE_RESCUE
```

When source review is requested, it stops before PDF acquisition with
`NEEDS_SOURCE_REVIEW`; this preserves high-priority paywalled candidates for
manual legal rescue instead of treating lack of access as lack of relevance.

## Fallback Policy

Normal acquisition order:

1. direct PDF URL
2. PMC OA PDF or archive
3. EuropePMC/OpenAlex source-native OA
4. Unpaywall
5. CORE/OpenAIRE and repository locations (new EZ acquisition)
6. optional Anna's Archive fallback with an expiring source-specific receipt

Anna-acquired PDFs must keep:

- `pdf_source: "anna_archive"`
- `acquisition_policy: "non_oa_fallback"`
- `fallback_after`
- `consent_id` and the actual acquisition attempts

## Validation

Use these checks before committing:

```powershell
python scripts/validate.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_validation.ps1
```
