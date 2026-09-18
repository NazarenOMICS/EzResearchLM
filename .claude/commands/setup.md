# /setup

Act as EZ. Read `AGENTS.md`, `SETUP.md`, and `docs/ez-host-operator.md` and use
`ez setup --check`, followed by `ez setup` when configuration is missing.
Prepare a local installation if this is a new clone. Preserve existing settings;
QMD is optional. The user completes NotebookLM login in their browser. Do not ask
them to create JSON files or configure another model API. Explain capabilities
and the next action in their language; setup success is not evidence of an E2E.
Start with the first-conversation guidance in `docs/ez-host-operator.md`. Show the
three user steps (prepare, sign in, ask a question), the effective output folder,
and point to `ez --guide`. Never imply that `ez` opens a standalone chat or that
closing the host conversation leaves an autonomous investigation running.

The steps below are **legacy reference only** for an explicitly selected old
wrapper workflow. They do not apply to normal EZ onboarding.

Help the user configure EZresearchLM.

Steps:

1. Read `README.md`, `SETUP.md`, and `CLAUDE.md`.
2. Check whether `.env` exists.
3. If `.env` is missing, suggest copying `.env.example`.
4. Ask where the user wants outputs saved:
   - run state and logs: `EZRESEARCH_RUNS_ROOT`
   - search metadata and PDFs: `EZRESEARCH_SEARCH_ROOT`
   - imported notes/vault: `EZRESEARCH_VAULT`
5. For a new clone, run the setup checker and installer:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -Install
```

This creates `.venv`, installs the local package, creates `.env` if needed, and
persists `EZRESEARCH_PYTHON=.venv\Scripts\python.exe`.

6. If dependencies are already installed, run only the checker:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

7. If the user gives custom paths, run for example:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" `
  -InitEnv `
  -Install `
  -RunsRoot "D:\ezresearch-runs" `
  -SearchRoot "E:\ezresearch-paper-cache" `
  -Vault "D:\ezresearch-vault"
```

8. If NotebookLM auth fails, run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
```

9. Run the checker again and report readiness.
10. Do not start a real research run until the user has a question, query file,
   and optional must-have file.

Output a short setup checklist, detected paths, missing dependencies, and exact
next commands.
