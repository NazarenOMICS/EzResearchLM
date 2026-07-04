param(
    [switch]$InitEnv,
    [switch]$Install,
    [string]$RunsRoot,
    [string]$SearchRoot,
    [string]$Vault,
    [string]$Python,
    [switch]$SkipNotebookLM,
    [switch]$SkipQmd,
    [switch]$RequireFullPipeline,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"

function Read-DotEnv {
    param([string]$Path)
    $values = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path)) { return $values }
    Get-Content -LiteralPath $Path -Encoding utf8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
        $name, $value = $line.Split("=", 2)
        $values[$name.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
    return $values
}

function Write-DotEnv {
    param([System.Collections.IDictionary]$Values)
    $lines = @(
        "# EZresearchLM local configuration",
        "# Do not commit this file.",
        ""
    )
    foreach ($key in $Values.Keys) {
        $lines += "$key=$($Values[$key])"
    }
    Set-Content -LiteralPath $EnvFile -Encoding utf8 -Value $lines
}

function Get-ConfigValue {
    param([System.Collections.IDictionary]$Values, [string]$Name, [string]$Default = "")
    $processValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($processValue) { return $processValue }
    if ($Values.Contains($Name) -and $Values[$Name]) { return $Values[$Name] }
    return $Default
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if ($InitEnv -and -not (Test-Path -LiteralPath $EnvFile)) {
    if (Test-Path -LiteralPath $EnvExample) {
        Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    } else {
        Set-Content -LiteralPath $EnvFile -Encoding utf8 -Value @("# EZresearchLM local configuration")
    }
}

$envValues = Read-DotEnv $EnvFile
if ($Install) {
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & python -m venv (Join-Path $Root ".venv")
        if ($LASTEXITCODE -ne 0) { throw "python -m venv failed" }
    }
    & $venvPython -m pip install -U pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
    & $venvPython -m pip install -e $Root
    if ($LASTEXITCODE -ne 0) { throw "pip install -e failed" }
    $envValues["EZRESEARCH_PYTHON"] = ".venv\Scripts\python.exe"
}
if ($RunsRoot) { $envValues["EZRESEARCH_RUNS_ROOT"] = $RunsRoot }
if ($SearchRoot) { $envValues["EZRESEARCH_SEARCH_ROOT"] = $SearchRoot }
if ($Vault) { $envValues["EZRESEARCH_VAULT"] = $Vault }
if ($Python) { $envValues["EZRESEARCH_PYTHON"] = $Python }
if ($Install -or $RunsRoot -or $SearchRoot -or $Vault -or $Python) {
    Write-DotEnv $envValues
}

$runsRoot = Get-ConfigValue $envValues "EZRESEARCH_RUNS_ROOT" (Join-Path $Root "runs")
$searchRoot = Get-ConfigValue $envValues "EZRESEARCH_SEARCH_ROOT" (Join-Path $Root "Search")
$vaultRoot = Get-ConfigValue $envValues "EZRESEARCH_VAULT" $Root
$pythonCandidates = @(
    (Get-ConfigValue $envValues "EZRESEARCH_PYTHON" ""),
    (Join-Path $Root ".venv\Scripts\python.exe"),
    "python"
) | Where-Object { $_ }
$pythonExe = @($pythonCandidates | Where-Object { $_ -eq "python" -or (Test-Path -LiteralPath $_) } | Select-Object -First 1)[0]

foreach ($dir in @($runsRoot, $searchRoot, $vaultRoot)) {
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
}

$checks = [ordered]@{
    root = $Root
    env_file = $EnvFile
    env_exists = (Test-Path -LiteralPath $EnvFile)
    runs_root = $runsRoot
    search_root = $searchRoot
    vault = $vaultRoot
    python = $pythonExe
    python_ok = $false
    paper_search_import_ok = $false
    notebooklm_cli_ok = $false
    notebooklm_auth_ok = $false
    qmd_cli_ok = $false
    qmd_collection_ok = $false
}

if ($pythonExe) {
    $paperSearchPath = Join-Path $Root "packages\paper_search"
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = if ($oldPythonPath) { "$paperSearchPath;$oldPythonPath" } else { $paperSearchPath }
    try {
        & $pythonExe --version | Out-Null
        $checks.python_ok = ($LASTEXITCODE -eq 0)
        & $pythonExe -c "import search_topic; print('ok')" | Out-Null
        $checks.paper_search_import_ok = ($LASTEXITCODE -eq 0)
    } catch {
        $checks.python_ok = $false
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }
}

$checks.notebooklm_cli_ok = Test-Command "notebooklm"
if ($checks.notebooklm_cli_ok -and -not $SkipNotebookLM) {
    try {
        & notebooklm list | Out-Null
        $checks.notebooklm_auth_ok = ($LASTEXITCODE -eq 0)
    } catch {
        $checks.notebooklm_auth_ok = $false
    }
}

$checks.qmd_cli_ok = Test-Command "qmd"
if ($checks.qmd_cli_ok -and -not $SkipQmd) {
    Push-Location $vaultRoot
    try {
        & qmd collection list | Out-Null
        $checks.qmd_collection_ok = ($LASTEXITCODE -eq 0)
    } catch {
        $checks.qmd_collection_ok = $false
    } finally {
        Pop-Location
    }
}

$requiredOk = $checks.python_ok -and $checks.paper_search_import_ok
$optionalOk = ($SkipNotebookLM -or ($checks.notebooklm_cli_ok -and $checks.notebooklm_auth_ok)) -and ($SkipQmd -or ($checks.qmd_cli_ok -and $checks.qmd_collection_ok))
$checks.ready_for_search = $requiredOk
$checks.ready_for_full_pipeline = ($requiredOk -and $optionalOk)

if ($Json) {
    $checks | ConvertTo-Json -Depth 5
    $exitOk = if ($RequireFullPipeline) { $checks.ready_for_full_pipeline } else { $checks.ready_for_search }
    exit ($(if ($exitOk) { 0 } else { 1 }))
}

Write-Host "EZresearchLM setup check"
Write-Host "Root: $Root"
Write-Host "Env: $EnvFile"
Write-Host "Runs root: $runsRoot"
Write-Host "Search root: $searchRoot"
Write-Host "Vault: $vaultRoot"
Write-Host "Python: $pythonExe"
Write-Host ""
foreach ($key in $checks.Keys) {
    if ($key -match "_ok$|_exists$|ready_") {
        $value = $checks[$key]
        $label = if ($value) { "OK" } else { "MISSING" }
        Write-Host ("{0,-28} {1}" -f $key, $label)
    }
}
Write-Host ""
if (-not $checks.notebooklm_auth_ok -and -not $SkipNotebookLM) {
    Write-Host "NotebookLM auth fix:"
    Write-Host "powershell.exe -ExecutionPolicy Bypass -File `"$Root\scripts\auto_login.ps1`""
}
if (-not $checks.ready_for_full_pipeline) {
    Write-Host "Search-only readiness may still be OK; full pipeline needs NotebookLM and QMD."
    Write-Host "Use -RequireFullPipeline when a run must reach NotebookLM QA."
}

$exitOk = if ($RequireFullPipeline) { $checks.ready_for_full_pipeline } else { $checks.ready_for_search }
exit ($(if ($exitOk) { 0 } else { 1 }))
