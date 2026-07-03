# Configuration

Wrappers load `.env` from the repository root when present. Existing process
environment variables win over `.env` values.

## Core Variables

- `EZRESEARCH_ROOT`: repository root override.
- `EZRESEARCH_VAULT`: vault/output root override. Defaults to repository root.
- `EZRESEARCH_PYTHON`: Python executable override.
- `NOTEBOOKLM_STORAGE_STATE`: NotebookLM browser auth storage path.

## Search Variables

- `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`: enables Unpaywall lookup.
- `NCBI_EMAIL`: polite PubMed/NCBI email.
- `NCBI_API_KEY`: optional NCBI API key.
- `PAPER_SEARCH_MCP_PLAYWRIGHT_CHROMIUM`: optional Chromium executable for Anna fallback.

## Optional Model Keys

- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`

Do not commit `.env`.
