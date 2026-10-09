# EZresearchLM Delivery Audit

Date: 2026-07-03

## Source Workspace

The existing local research workspace was used as the migration source and left
dirty and intact. EZresearchLM was created in a new folder and initialized as an
independent deliverable.

## Included

- Core PowerShell wrappers under `scripts/`.
- Paper discovery/acquisition code under `packages/paper_search/`.
- NotebookLM helper scripts under `notebooklm/scripts/`.
- Minimal docs under `docs/`.
- Example JSON inputs under `examples/`.
- Empty runtime folders with `.gitkeep`.
- MIT license.

## Excluded

- Git history from nested source repositories.
- Virtual environments and caches.
- PDFs and downloaded paper archives.
- Run outputs and NotebookLM source exports.
- QA answer payloads and passage maps.
- Browser auth state and cookies.
- `client_secret*.json`, `token.json`, and `.env`.
- Legacy UI and unrelated local workspace artifacts.
- Network-heavy upstream tests.

## Sanitization

- Replaced hardcoded source workspace paths with repository-root resolution.
- Added `.env` loading for wrappers.
- Added `.env.example` with non-secret placeholders.
- Replaced personal writing rules with a generic academic evidence style guide.
- Rewrote public docs without personal thesis context.
- Removed the legacy MCP server download surface from the deliverable package.
- Kept Anna's Archive documented as optional acquisition fallback only.

## Validation Commands Run

PowerShell parse:

```powershell
$scripts = Get-ChildItem -LiteralPath .\scripts -Filter *.ps1
foreach ($script in $scripts) {
  $errs = $null
  $null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -LiteralPath $script.FullName -Raw), [ref]$errs)
  if ($errs.Count -gt 0) { throw $script.Name }
}
```

Python compile:

```powershell
$env:PYTHONPATH = "$PWD\packages\paper_search"
python -m py_compile .\packages\paper_search\search_topic.py .\packages\paper_search\run_search_topic_wrapper.py .\packages\paper_search\paper_search_mcp\academic_platforms\anna_archive.py
```

Unit tests:

```powershell
$env:PYTHONPATH = "$PWD\packages\paper_search"
python -m unittest discover -s .\packages\paper_search\tests
```

Secret/data scan:

```powershell
Get-ChildItem -Recurse -Force | Where-Object {
  $_.Name -match 'client_secret|token\.json|storage_state|\.env$|cookie' -or
  $_.Extension -in @('.pdf','.tgz','.zip','.tar')
}
```

## Results

- PowerShell parse: passed for all scripts.
- Python compile: passed with the dependency-ready project interpreter.
- Unit tests: 11 passed.
- Secret/data scan: no committed secret/data files found before git init.

## Remaining Risks

- NotebookLM integration requires an authenticated local browser profile.
- Full end-to-end QA was not run to avoid creating real notebooks or spending
  external service usage.
- Anna fallback was covered by unit tests/mocks, not by a real download.
- QMD must be installed/configured in the target environment for answer reuse.

## GitHub Readiness

The repository is ready for a private GitHub remote after final `git status`,
`git diff --check`, and tracked-file secret scan.

## 2026-07-04 Follow-up Audit

A second delivery pass found that `notebooklm/scripts/` existed but was empty in
the initial clean repository. This was a release-blocking issue because the
pipeline calls `list_sources_to_json.py`, `import_sources.py`, and
`batch_ask.py` after NotebookLM upload.

Fixes applied:

- Copied NotebookLM helper scripts into `notebooklm/scripts/`.
- Removed copied `__pycache__` runtime cache.
- Sanitized old machine-specific NotebookLM executable fallback in
  `batch_ask.py`; it now uses `NOTEBOOKLM_EXE` or `notebooklm` from PATH.
- Sanitized Gemini OAuth lookup in `generate_questions.py`; it now uses
  `EZRESEARCH_ROOT`, `.env`, or explicit OAuth environment variables instead of
  source-workspace paths.
- Changed EuropePMC PDF text extraction to import `PyPDF2` lazily, so basic
  paper-search unit tests can import the package without requiring PDF parsing
  dependencies until that feature is used.

Validation rerun:

- PowerShell parse: passed for all scripts in `scripts/`.
- Python compile: passed for edited paper-search and NotebookLM helper modules.
- Unit tests: 11 passed with a dependency-ready Python environment.
- `git diff --check`: passed.
- Tracked-file secret/data scan: no matches.
- Full-tree secret/data scan: no secret files, PDFs, archives, cookies, or auth
  state files found.

Remaining GitHub step:

- Local repository is ready. A private GitHub remote still requires the target
  repository URL or authenticated GitHub creation step.

## 2026-07-04 Acquisition Hardening

Follow-up fixes from the strong smoke audit were applied to the deliverable
repo:

- Anna fallback now has a per-identifier timeout controlled by
  `PAPER_SEARCH_MCP_ANNA_TIMEOUT_SECONDS` (default `120`).
- Search artifacts are written before acquisition and after every candidate, so
  `candidate-sources.json`, `source-rescue.json`, and `missing-sources.md`
  survive partial acquisition failures.
- Must-have identifiers and titles are searched before broad user queries.
- Required target matches are acquired before opportunistic candidates.
- Per-record acquisition exceptions become structured `failed / network`
  entries instead of aborting without rescue artifacts.
- `run_hermes_pipeline.ps1` records `search / running` before search and
  `search / failed_or_timed_out` on wrapper failure.

Validation rerun:

- Python compile: passed.
- Unit tests: 15 passed.
- PowerShell parse: passed for pipeline/search/doctor/answer wrappers.
- `git diff --check`: passed.
