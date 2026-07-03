# EZresearchLM Pipeline Reference

EZresearchLM builds traceable academic evidence sets. It separates source
acquisition from reasoning so that local code never becomes the truth engine.

## Model

- Paper search code discovers, normalizes, deduplicates, and acquires sources.
- NotebookLM reads imported sources and produces cited QA.
- QMD/local recall helps find already processed evidence.
- GPT agents can curate queries/questions and interpret summaries, but they must
  not create uncited bibliographic claims.

## Stages

1. `discover`: query academic providers.
2. `resolve`: normalize DOI, PMID, PMCID, title, year, journal, and authors.
3. `acquire`: download PDFs through open routes first.
4. `rescue`: record missing or fallback-acquired sources.
5. `notebook`: upload acquired PDFs to NotebookLM.
6. `qa`: ask focused questions only after source readiness checks pass.
7. `audit`: inspect citation support and reusable summaries.

## Acquisition Order

1. direct PDF URL
2. PMC OA PDF or archive
3. EuropePMC/OpenAlex source-native OA
4. Unpaywall
5. optional Anna's Archive fallback

Anna fallback is disabled unless requested through the wrapper or source target
configuration. Anna is acquisition only. It never answers questions and never
removes the need for NotebookLM citation checks.

## Required Source Gate

Use `-MustHaveFile` for sources that must be present before QA. If any required
source is missing, the pipeline stops before NotebookLM QA with:

```text
NEEDS_SOURCE_RESCUE
```

The run leaves:

- `runs/<project>/<slug>/source-rescue.json`
- `runs/<project>/<slug>/missing-sources.md`
- `runs/<project>/<slug>/run-state.json`

## Commands

Create a source set:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "<slug>" `
  -Project "<project>" `
  -Goal "<goal>" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "<NotebookLM title>" `
  -Dashboard "<dashboard>"
```

Resume after questions are filled:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "<slug>" `
  -Project "<project>" `
  -Goal "<goal>" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "<NotebookLM title>" `
  -Dashboard "<dashboard>" `
  -SkipSearch `
  -FromExistingQuestions `
  -ExistingNotebookId "<NotebookLM id>"
```

Diagnose a run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "<project>" `
  -Slug "<slug>"
```

## Failure States

- `NEEDS_CORPUS`: existing evidence is insufficient for the question.
- `NEEDS_SOURCE_RESCUE`: required sources are missing before QA.
- `NEEDS_QUESTIONS`: sources are imported, but focused QA questions are missing.
- `NEEDS_MORE_QA`: evidence exists, but the NotebookLM answer is too shallow or
  citations do not support the claim.
- `manual_needed`: the source is identified but not acquired automatically.
