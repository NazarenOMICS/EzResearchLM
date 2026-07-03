# EZresearchLM

EZresearchLM is a NotebookLM-centered evidence pipeline for academic research.
It turns scattered literature searches into a reusable, traceable evidence base
with explicit source status, recoverable runs, and cited QA outputs.

The system is intentionally conservative: search and local code can discover,
normalize, acquire, and organize sources, but thesis-ready claims must come from
NotebookLM answers over imported documents.

## What It Does

- Searches academic sources such as PubMed, EuropePMC, OpenAlex, Semantic
  Scholar, and Crossref.
- Normalizes bibliographic metadata such as DOI, PMID, PMCID, title, year,
  journal, and authors.
- Deduplicates candidates and records acquisition provenance.
- Downloads open PDFs when available.
- Optionally tries Anna's Archive only after open-access routes fail.
- Tracks missing required sources in `source-rescue.json`.
- Uploads acquired PDFs to NotebookLM.
- Exports NotebookLM answers, summaries, source curation, and citation audits.
- Uses QMD/local recall to reuse already processed evidence before creating new
  source sets.

## Architecture

```text
discover -> resolve -> acquire -> notebook -> qa -> audit
```

- `discover`: query multiple academic sources.
- `resolve`: normalize identifiers and source metadata.
- `acquire`: download PDFs through open routes first, then optional fallback.
- `notebook`: upload only acquired PDFs to NotebookLM.
- `qa`: ask focused NotebookLM questions.
- `audit`: inspect citation support and reusable summaries.

## Quick Start

1. Create a virtual environment and install dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

2. Copy `.env.example` to `.env` and fill only the values you need.

```powershell
Copy-Item .env.example .env
```

3. Check NotebookLM auth.

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
```

4. Run a source acquisition pipeline.

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "example-topic" `
  -Project "general" `
  -Goal "Build an evidence set for an example academic question" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "EZresearchLM example" `
  -Dashboard "EZresearchLM example dashboard" `
  -MustHaveFile ".\examples\must-have.example.json" `
  -AllowAnnaFallback
```

If required sources are missing, the run stops before QA with
`NEEDS_SOURCE_RESCUE`.

## Debugging

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "general" `
  -Slug "example-topic"
```

The doctor reports discovered candidates, downloaded PDFs, Anna fallback
attempts, missing required sources, NotebookLM source readiness, QA status, and
the resume command.

## Safety Model

- NotebookLM is the evidence engine.
- QMD/local search is recall only.
- Anna's Archive is an acquisition fallback only.
- Missing sources stay visible as `manual_needed`.
- Run artifacts and PDFs are ignored by Git.
- Secrets and cookies must stay in `.env` or external auth storage, never in the
  repository.

## Validation

```powershell
python -m py_compile .\packages\paper_search\search_topic.py .\packages\paper_search\run_search_topic_wrapper.py
python -m unittest discover -s .\packages\paper_search\tests
```

## Repository Status

This repository is designed to be private-first. Before making it public, review
`docs/github-delivery-checklist.md` and run the secret/data checks listed there.
