# Debugging

## Parse PowerShell

```powershell
$errs = $null
$null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw .\scripts\run_hermes_pipeline.ps1), [ref]$errs)
$errs
```

Repeat for every script under `scripts/`.

## Compile Python

```powershell
python -m py_compile .\packages\paper_search\search_topic.py .\packages\paper_search\run_search_topic_wrapper.py
```

## Unit Tests

```powershell
$env:PYTHONPATH = "$PWD\packages\paper_search"
python -m unittest discover -s .\packages\paper_search\tests
```

## Doctor

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" -Project general -Slug example-topic
```

Use the doctor first after a timeout, NotebookLM crash, upload failure, or
interrupted QA run.

## Secret Scan

```powershell
git ls-files | Select-String -Pattern "secret|token|cookie|storage_state|\.env|\.pdf"
```
