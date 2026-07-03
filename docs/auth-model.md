# Auth Model

EZresearchLM has two separate credential surfaces:

- NotebookLM browser auth, stored outside the repository.
- Optional API keys for scholarly helpers or model providers, loaded from
  environment variables or `.env`.

Never commit:

- `.env`
- `client_secret*.json`
- `token.json`
- NotebookLM `storage_state.json`
- browser cookies

NotebookLM auth can be refreshed with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
```

Use `NOTEBOOKLM_STORAGE_STATE` when the default profile path is not appropriate.
