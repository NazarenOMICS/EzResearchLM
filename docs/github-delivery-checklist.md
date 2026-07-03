# GitHub Delivery Checklist

Run this before pushing or making the repository public.

## Required

- `git status --short` shows only intended files.
- No real PDFs, source exports, QA answers, run payloads, or notebooks are tracked.
- No `.env`, token files, browser cookies, or NotebookLM auth state are tracked.
- PowerShell scripts parse successfully.
- Python files compile.
- Unit tests pass.
- README quick start is current.
- `docs/source-rescue.md` matches the actual JSON contract.
- Anna fallback is documented as optional acquisition only.

## Commands

```powershell
git status --short
git diff --check
git ls-files | Select-String -Pattern "secret|token|cookie|storage_state|\.env|\.pdf|client_secret"
python -m py_compile .\packages\paper_search\search_topic.py .\packages\paper_search\run_search_topic_wrapper.py
$env:PYTHONPATH = "$PWD\packages\paper_search"
python -m unittest discover -s .\packages\paper_search\tests
```

## Private First

Keep the first GitHub remote private. Review paths, examples, and documentation
again before making the repository public.
