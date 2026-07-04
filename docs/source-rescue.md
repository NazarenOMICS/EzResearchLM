# Source Rescue

`source-rescue.json` is the retryable state queue for source acquisition and
NotebookLM readiness. It replaces log scraping.

## Location

```text
runs/<project>/<slug>/source-rescue.json
Search/<project>/<slug>-papers/source-rescue.json
```

The pipeline syncs the search copy into the run directory.

## Entry Shape

```json
{
  "target_id": "PMID:123456",
  "title": "Example title",
  "doi": "10.0000/example",
  "pmid": "123456",
  "pmcid": "",
  "required": true,
  "status": "downloaded",
  "failure_reason": null,
  "pdf_source": "unpaywall",
  "pdf_path": "Search/project/slug-papers/example.pdf",
  "notebook_source_id": "",
  "notes": []
}
```

## Status Values

- `downloaded`: local PDF passed validation.
- `notebook_ready`: NotebookLM lists the source as ready.
- `manual_needed`: source is identified but still unavailable.
- `failed`: acquisition or upload failed in a recoverable way.

## Failure Reasons

- `paywall`
- `network`
- `no_match`
- `anna_failed`
- `upload_failed`

## Anna Provenance

When Anna's Archive is used, the source must remain visibly marked:

```json
{
  "pdf_source": "anna_archive",
  "acquisition_policy": "non_oa_fallback",
  "fallback_after": ["direct", "pmc_oa", "europepmc_openalex", "unpaywall", "core_openaire_semantic"]
}
```

If Anna fails, keep the source as `manual_needed`; do not convert it into an
uncited answer.

Anna attempts are bounded by `PAPER_SEARCH_MCP_ANNA_TIMEOUT_SECONDS` (default
`120`). Search writes `candidate-sources.json`, `source-rescue.json`, and
`missing-sources.md` before acquisition starts and after each candidate, so a
timeout or crash still leaves a recoverable rescue queue.
