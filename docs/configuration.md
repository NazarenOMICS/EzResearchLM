# Configuration

Wrappers load `.env` from the repository root when present. Existing process
environment variables win over `.env` values.

## Core Variables

- `EZRESEARCH_ROOT`: repository root override.
- `EZRESEARCH_VAULT`: vault/output root override. Defaults to repository root.
- `EZRESEARCH_PYTHON`: Python executable override.
- `EZRESEARCH_RUNS_ROOT`: where pipeline state, logs, questions, and rescue
  queues are written. Defaults to `runs/` under the repository.
- `EZRESEARCH_SEARCH_ROOT`: where search metadata and downloaded/acquired PDFs
  are written. Defaults to `Search/` under the repository.
- `NOTEBOOKLM_STORAGE_STATE`: NotebookLM browser auth storage path.

Example:

```powershell
EZRESEARCH_RUNS_ROOT=D:\research-runs
EZRESEARCH_SEARCH_ROOT=E:\paper-cache
```

You can also override one run directly with `-SaveDir`:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_search_topic.ps1" `
  -Slug "membrane-stress" `
  -QueriesFile ".\examples\queries.example.json" `
  -SaveDir "E:\paper-cache\membrane-stress"
```

## Search Variables

- `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`: enables Unpaywall lookup.
- `NCBI_EMAIL`: polite PubMed/NCBI email.
- `NCBI_API_KEY`: optional NCBI API key.
- `PAPER_SEARCH_MCP_PLAYWRIGHT_CHROMIUM`: optional Chromium executable for Anna fallback.
- `PAPER_SEARCH_MCP_ANNA_TIMEOUT_SECONDS`: per-identifier Anna fallback timeout;
  defaults to `120`.

## Optional Model Keys

- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`

Do not commit `.env`.
