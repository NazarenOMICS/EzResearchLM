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
- `upload_failed`

## Sources Without Open Access

Anna's Archive is not supported. A paywalled source stays `manual_needed`; the
user can import a PDF they already have with `ez rescue <run> --source <id>
--import <pdf>`, which records its origin. Older runs may still show
`pdf_source: "anna_archive"`; that provenance is kept as history.

Search writes `candidate-sources.json`, `source-rescue.json`, and
`missing-sources.md` before acquisition starts and after each candidate, so a
timeout or crash still leaves a recoverable rescue queue.
