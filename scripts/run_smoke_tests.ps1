param(
    [switch]$SkipNetwork,
    [switch]$IncludeClaude,
    [switch]$IncludeFullPipelinePreflight,
    [string]$ReportPath
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ezresearch-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null

function Invoke-SmokeStep {
    param(
        [string]$Name,
        [scriptblock]$Command,
        [int[]]$AllowedExitCodes = @(0)
    )
    $started = Get-Date
    $output = ""
    $exitCode = 0
    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 0
        $output = & $Command 2>&1 | Out-String
        $exitCode = if ($null -ne $global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
    } catch {
        $output = ($_ | Out-String)
        $exitCode = if ($null -ne $global:LASTEXITCODE -and $global:LASTEXITCODE -ne 0) { [int]$global:LASTEXITCODE } else { 1 }
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
    $ok = $AllowedExitCodes -contains $exitCode
    [pscustomobject]@{
        name = $Name
        status = if ($ok) { "pass" } else { "fail" }
        exit_code = $exitCode
        allowed_exit_codes = $AllowedExitCodes
        duration_seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 2)
        output_tail = (($output -split "`r?`n") | Where-Object { $_ } | Select-Object -Last 20) -join "`n"
    }
}

$results = New-Object System.Collections.Generic.List[object]

$results.Add((Invoke-SmokeStep "setup-search-only" {
    powershell.exe -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\setup_ezresearch.ps1") -InitEnv -SkipNotebookLM -SkipQmd -Json
}))

if ($IncludeClaude) {
    $results.Add((Invoke-SmokeStep "setup-claude-state" {
        powershell.exe -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\setup_ezresearch.ps1") -CheckClaude -SkipNotebookLM -SkipQmd -Json
    }))
}

$results.Add((Invoke-SmokeStep "powershell-parse" {
    $files = Get-ChildItem (Join-Path $Root "scripts") -Filter "*.ps1"
    foreach ($file in $files) {
        $errs = $null
        $null = [System.Management.Automation.PSParser]::Tokenize(
            (Get-Content -LiteralPath $file.FullName -Raw),
            [ref]$errs
        )
        if ($errs.Count -gt 0) { throw "PowerShell parse failed for $($file.Name)" }
    }
    "PowerShell parse OK ($($files.Count) files)"
}))

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

$results.Add((Invoke-SmokeStep "python-compile" {
    & $python -m py_compile `
        (Join-Path $Root "packages\paper_search\search_topic.py") `
        (Join-Path $Root "packages\paper_search\run_search_topic_wrapper.py")
}))

$results.Add((Invoke-SmokeStep "unit-tests" {
    & $python -m unittest discover -s (Join-Path $Root "packages\paper_search\tests")
}))

$results.Add((Invoke-SmokeStep "doctor-nonexistent-run" {
    powershell.exe -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\run_hermes_doctor.ps1") `
        -Project "smoke-runs" `
        -Slug "nonexistent-smoke"
}))

if (-not $SkipNetwork) {
    $scoutDir = Join-Path $TempRoot "scout"
    $results.Add((Invoke-SmokeStep "search-scout-crossref" {
        powershell.exe -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\run_search_topic.ps1") `
            -Slug "scout-smoke" `
            -QueriesFile (Join-Path $Root "examples\queries.example.json") `
            -SaveDir $scoutDir `
            -Sources "crossref" `
            -TopN 1 `
            -ScoutOnly `
            -StdoutJson
    }))

    $resolveDir = Join-Path $TempRoot "resolve"
    $results.Add((Invoke-SmokeStep "resolve-must-have-rescue" {
        powershell.exe -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\run_search_topic.ps1") `
            -Slug "resolve-smoke" `
            -QueriesFile (Join-Path $Root "examples\queries.example.json") `
            -MustHaveFile (Join-Path $Root "examples\must-have.example.json") `
            -SaveDir $resolveDir `
            -Sources "crossref" `
            -TopN 1 `
            -ResolveOnly `
            -StdoutJson
        $rescuePath = Join-Path $resolveDir "source-rescue.json"
        if (-not (Test-Path -LiteralPath $rescuePath)) { throw "source-rescue.json missing" }
        $rescue = Get-Content -LiteralPath $rescuePath -Raw | ConvertFrom-Json
        $manual = @($rescue.sources | Where-Object { $_.status -eq "manual_needed" })
        if ($manual.Count -lt 1) { throw "expected at least one manual_needed source" }
    }))
}

if ($IncludeFullPipelinePreflight) {
    $emptyPdfDir = Join-Path $TempRoot "empty-pdfs"
    New-Item -ItemType Directory -Force -Path $emptyPdfDir | Out-Null
    $results.Add((Invoke-SmokeStep "pipeline-preflight-auth-gate" {
        powershell.exe -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\run_hermes_pipeline.ps1") `
            -Slug "empty-pdf-smoke" `
            -Project "smoke-runs" `
            -Goal "Smoke test empty PDF stop" `
            -QueriesFile (Join-Path $Root "examples\queries.example.json") `
            -NotebookTitle "Smoke" `
            -Dashboard "Smoke" `
            -SaveDir $emptyPdfDir `
            -SkipSearch `
            -SkipBatch
    } @(1, 2)))
}

$summary = [pscustomobject]@{
    date = (Get-Date).ToString("s")
    root = $Root
    temp_root = $TempRoot
    skip_network = [bool]$SkipNetwork
    include_claude = [bool]$IncludeClaude
    include_full_pipeline_preflight = [bool]$IncludeFullPipelinePreflight
    passed = @($results | Where-Object { $_.status -eq "pass" }).Count
    failed = @($results | Where-Object { $_.status -eq "fail" }).Count
    results = $results
}

foreach ($result in $results) {
    $marker = if ($result.status -eq "pass") { "PASS" } else { "FAIL" }
    Write-Host ("[{0}] {1} ({2}s)" -f $marker, $result.name, $result.duration_seconds)
    if ($result.status -eq "fail") {
        Write-Host $result.output_tail
    }
}
Write-Host ("Smoke summary: {0} passed, {1} failed" -f $summary.passed, $summary.failed)

if ($ReportPath) {
    $parent = Split-Path -Parent $ReportPath
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8
    Write-Host "Report: $ReportPath"
}

exit ($(if ($summary.failed -eq 0) { 0 } else { 1 }))
