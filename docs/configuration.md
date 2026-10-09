# Configuration

EZ reads optional settings from environment variables and from a `.env` file in the
repository root. Process environment variables win over `.env` values. Do not commit
`.env`.

## EZ

- `EZRESEARCH_RUNS_ROOT`: where runs are written. Defaults to `~/.ezresearch/runs`;
  projects, inboxes and reports live next to it (see `carpetas.md`). The same folder
  can be given per command with `--root`.
- `EZRESEARCH_ROOT`: location of the EZ installation (guides and setup reference).
  Only needed for unusual installs.

## Search and acquisition

- `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`: contact email that Unpaywall requires. Usually
  saved once with `ez setup --unpaywall-email <email>`.
- `NCBI_EMAIL` and `NCBI_API_KEY`: optional, for polite and faster PubMed requests.
- `SEMANTIC_SCHOLAR_API_KEY`: optional. Without it Semantic Scholar often answers
  HTTP 429; EZ records that query as failed and continues with the other providers.
- `EZRESEARCH_CORE_API_KEY`: optional, sent to the CORE API when an acquisition route uses it.

## NotebookLM

Sign-in is stored by `notebooklm-py` outside the repository. `ez setup --check` shows
the login command when it is needed; the person completes it in their browser. The
agent never reads or copies cookies.
