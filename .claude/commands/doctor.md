# /doctor

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
