# /setup

Help the user configure EZresearchLM.

Steps:

1. Read `README.md`, `SETUP.md`, and `CLAUDE.md`.
2. Check whether `.env` exists.
3. If `.env` is missing, suggest copying `.env.example`.
4. Ask where the user wants outputs saved:
   - run state and logs: `EZRESEARCH_RUNS_ROOT`
   - search metadata and PDFs: `EZRESEARCH_SEARCH_ROOT`
   - imported notes/vault: `EZRESEARCH_VAULT`
5. Check Python:
   - prefer `EZRESEARCH_PYTHON`;
   - otherwise `.venv\Scripts\python.exe`;
   - otherwise `python`.
6. Check NotebookLM auth with `notebooklm list`.
7. If auth fails, run `.\scripts\auto_login.ps1`.
8. Do not start a real research run until the user has a question, query file,
   and optional must-have file.

Output a short setup checklist and exact commands.
