# EZresearchLM Agent Guide

EZresearchLM is a NotebookLM-centered evidence pipeline for academic research.
It discovers papers, acquires PDFs, builds a traceable source set, asks
NotebookLM focused questions, exports cited answers, and keeps enough run state
to debug or resume interrupted work.

## Core Rules

- NotebookLM is the evidence and QA engine.
- Local search and QMD are recall/acquisition helpers, not answer engines.
- Do not write strong bibliographic claims from memory.
- If evidence is missing, emit `NEEDS_CORPUS`, `NEEDS_MORE_QA`, or
  `NEEDS_SOURCE_RESCUE`.
- Anna's Archive is an optional acquisition fallback only. It must never answer
  questions or erase provenance.
- Do not commit real PDFs, notebooks, tokens, cookies, source exports, or run
  artifacts.

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

## Main Commands

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
- `run-state.json`

If required sources are missing, the pipeline stops before NotebookLM QA with:

```text
NEEDS_SOURCE_RESCUE
```

## Fallback Policy

Normal acquisition order:

1. direct PDF URL
2. PMC OA PDF or archive
3. EuropePMC/OpenAlex source-native OA
4. Unpaywall
5. optional Anna's Archive fallback

Anna-acquired PDFs must keep:

- `pdf_source: "anna_archive"`
- `acquisition_policy: "non_oa_fallback"`
- `fallback_after`

## Validation

Use these checks before committing:

```powershell
python -m py_compile .\packages\paper_search\search_topic.py .\packages\paper_search\run_search_topic_wrapper.py
python -m unittest discover -s .\packages\paper_search\tests
```
