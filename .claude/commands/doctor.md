# /doctor

Act as EZ. Use the run ID or path already available in the conversation and run
`ez doctor <corrida> --json`. Explain what is verifiable, what failed and the next
action in the user's language. Do not infer academic validity from a local PASS.
If the run is legacy, inspect it without implicit migration; show a migration
preview only when relevant. Follow `docs/ez-host-operator.md` for recovery.

The commands below are **legacy reference only**, when operating a run with its
original wrappers. Do not ask for project/slug again if its path is already known.

Diagnose an EZresearchLM run.

Ask the user for:

- `Project`
- `Slug`

Then run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "<project>" `
  -Slug "<slug>"
```

Report:

- run stage/status;
- candidate count;
- downloaded PDFs;
- missing must-have sources;
- NotebookLM notebook id;
- QA/citation audit state;
- exact resume command.

Do not manually hunt sources unless the user explicitly asks.
