param(
    [string]$Python
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

if (-not $Python) {
    $candidates = @(
        (Join-Path $ROOT ".venv\Scripts\python.exe"),
        $env:EZRESEARCH_PYTHON,
        "python"
    ) | Where-Object { $_ }
    $Python = @($candidates | Where-Object { $_ -eq "python" -or (Test-Path -LiteralPath $_) } | Select-Object -First 1)[0]
}

if (-not $Python) {
    Write-Host "[FAIL] No Python interpreter found" -ForegroundColor Red
    exit 1
}

$paperSearchPath = Join-Path $ROOT "packages\paper_search"
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$paperSearchPath;$env:PYTHONPATH" } else { $paperSearchPath }

Write-Host "[validation] Python: $Python"
Write-Host "[validation] PYTHONPATH: $env:PYTHONPATH"

& $Python (Join-Path $ROOT "scripts\validate.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$files = @(Get-ChildItem (Join-Path $ROOT "scripts") -Filter *.ps1) + @(Get-ChildItem (Join-Path $ROOT "notebooklm\scripts") -Filter *.ps1)
foreach ($file in $files) {
    $tokens = $null
    $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw "PowerShell parse failed: $($file.Name): $errors" }
}
Write-Host "[validation] PowerShell parse OK ($($files.Count) files)"
exit 0
