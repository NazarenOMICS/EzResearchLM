param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [Parameter(Mandatory = $true)]
    [string]$Slug,

    [string]$VaultSlug,
    [string]$SearchRoot
)

$ErrorActionPreference = "Stop"
$EZRESEARCH_ROOT = if ($env:EZRESEARCH_ROOT) { $env:EZRESEARCH_ROOT } else { Split-Path -Parent $PSScriptRoot }
$ENV_FILE = Join-Path $EZRESEARCH_ROOT ".env"
if (Test-Path -LiteralPath $ENV_FILE) {
    Get-Content -LiteralPath $ENV_FILE -Encoding utf8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
        $name, $value = $line.Split("=", 2)
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($name -and -not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}
$AUTORESEARCH = $EZRESEARCH_ROOT
if (-not $SearchRoot) { $SearchRoot = Join-Path $EZRESEARCH_ROOT "Search" }
$RUN_DIR = Join-Path (Join-Path (Join-Path $AUTORESEARCH "runs") $Project) $Slug
$SAVE_DIR = Join-Path (Join-Path $SearchRoot $Project) "$Slug-papers"
$STATUS = Join-Path $RUN_DIR "STATUS.md"
$RUN_STATE = Join-Path $RUN_DIR "run-state.json"
$SOURCE_RESCUE = Join-Path $RUN_DIR "source-rescue.json"
$CANDIDATE_SOURCES = Join-Path $RUN_DIR "candidate-sources.json"
$MISSING_SOURCES = Join-Path $RUN_DIR "missing-sources.md"
$TMP_SOURCES = Join-Path $RUN_DIR "tmp-sources-$Slug.json"
$QUESTIONS_FILE = Join-Path $RUN_DIR "questions-$Slug.json"
$UPLOAD_LOG = Join-Path $RUN_DIR "upload-log-$Slug.txt"

if (-not $VaultSlug) { $VaultSlug = "$Project/$Slug" }

function Read-JsonOrNull {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding utf8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Count-Items {
    param([object]$Payload, [string[]]$Fields)
    if (-not $Payload) { return 0 }
    if ($Payload -is [array]) { return @($Payload).Count }
    foreach ($field in $Fields) {
        if ($Payload.PSObject.Properties.Name -contains $field -and $Payload.$field) {
            return @($Payload.$field).Count
        }
    }
    return 0
}

function Get-NotebookId {
    param([object]$RunState, [string]$StatusPath, [object]$Questions)
    if ($RunState -and $RunState.notebook_id) { return [string]$RunState.notebook_id }
    if ($Questions -and $Questions.notebook_id) { return [string]$Questions.notebook_id }
    if (Test-Path -LiteralPath $StatusPath) {
        $text = Get-Content -LiteralPath $StatusPath -Raw -Encoding utf8
        $match = [regex]::Match($text, "(?m)^- Notebook ID:\s*([0-9a-fA-F-]{36})\s*$")
        if ($match.Success) { return $match.Groups[1].Value }
    }
    return ""
}

function Get-ResumeCommand {
    param([object]$RunState, [string]$NotebookId)
    if ($RunState -and $RunState.resume_command) { return [string]$RunState.resume_command }
    $parts = @(
        "powershell.exe -ExecutionPolicy Bypass -File `"$AUTORESEARCH\scripts\run_hermes_pipeline.ps1`"",
        "-Slug `"$Slug`"",
        "-Project `"$Project`""
    )
    if ($VaultSlug) { $parts += "-VaultSlug `"$VaultSlug`"" }
    if ($NotebookId) {
        $parts += "-SkipSearch"
        $parts += "-FromExistingQuestions"
        $parts += "-ExistingNotebookId `"$NotebookId`""
    }
    return ($parts -join " ")
}

$runState = Read-JsonOrNull $RUN_STATE
$rescue = Read-JsonOrNull $SOURCE_RESCUE
if (-not $rescue) {
    $searchRescue = Join-Path $SAVE_DIR "source-rescue.json"
    $rescue = Read-JsonOrNull $searchRescue
    if ($rescue) { $SOURCE_RESCUE = $searchRescue }
}
$candidates = Read-JsonOrNull $CANDIDATE_SOURCES
if (-not $candidates) {
    $searchCandidates = Join-Path $SAVE_DIR "candidate-sources.json"
    $candidates = Read-JsonOrNull $searchCandidates
    if ($candidates) { $CANDIDATE_SOURCES = $searchCandidates }
}
$sources = Read-JsonOrNull $TMP_SOURCES
$questions = Read-JsonOrNull $QUESTIONS_FILE
$notebookId = Get-NotebookId -RunState $runState -StatusPath $STATUS -Questions $questions

$rescueSources = if ($rescue -and $rescue.sources) { @($rescue.sources) } else { @() }
$downloaded = @($rescueSources | Where-Object { $_.status -in @("downloaded", "notebook_ready") })
$notebookReady = @($rescueSources | Where-Object { $_.status -eq "notebook_ready" })
$annaAttempts = @($rescueSources | Where-Object { $_.pdf_source -eq "anna_archive" -or $_.failure_reason -eq "anna_failed" })
$annaDownloads = @($rescueSources | Where-Object { $_.pdf_source -eq "anna_archive" })
$missingMustHave = @($rescueSources | Where-Object { $_.required -eq $true -and $_.status -notin @("downloaded", "notebook_ready") })
$failedUploads = @()
if (Test-Path -LiteralPath $UPLOAD_LOG) {
    $failedUploads = @(Get-Content -LiteralPath $UPLOAD_LOG -Encoding utf8 | Where-Object { $_ -match "FAIL\s+-\s+.+\.pdf\s*$" })
}

$qaDir = Join-Path (Join-Path (Join-Path (Join-Path (Join-Path $AUTORESEARCH "Notes") "NotebookLM") $VaultSlug) "QA") "summaries"
$qaSummaries = if (Test-Path -LiteralPath $qaDir) {
    @(Get-ChildItem -LiteralPath $qaDir -Filter "*QA Summary.md" -File -ErrorAction SilentlyContinue)
} else { @() }
$citationAudits = if (Test-Path -LiteralPath $qaDir) {
    @(Get-ChildItem -LiteralPath $qaDir -Filter "*Citation Audit.md" -File -ErrorAction SilentlyContinue)
} else { @() }

Write-Host "Hermes Doctor" -ForegroundColor Cyan
Write-Host "Run dir: $RUN_DIR"
Write-Host "Search dir: $SAVE_DIR"
Write-Host "Stage/status: $($runState.stage) / $($runState.status)"
Write-Host ""
Write-Host "Discovered candidates: $(Count-Items $candidates @('candidates', 'papers'))"
Write-Host "Downloaded PDFs: $($downloaded.Count)"
Write-Host "Notebook-ready sources: $($notebookReady.Count)"
Write-Host "Anna fallback attempts: $($annaAttempts.Count)"
Write-Host "Anna fallback downloads: $($annaDownloads.Count)"
Write-Host "Missing must-have sources: $($missingMustHave.Count)"
if ($missingMustHave.Count -gt 0) {
    foreach ($item in $missingMustHave) {
        Write-Host "- $($item.target_id) :: $($item.failure_reason) :: $($item.title)"
    }
}
Write-Host ""
Write-Host "NotebookLM notebook id: $notebookId"
Write-Host "NotebookLM exported sources: $(Count-Items $sources @('sources', 'items'))"
Write-Host "Upload failures: $($failedUploads.Count)"
Write-Host "Filled questions: $(if ($questions -and $questions.questions) { @($questions.questions | Where-Object { $_.question -and $_.question.Trim().Length -gt 0 }).Count } else { 0 })"
Write-Host "QA summaries: $($qaSummaries.Count)"
Write-Host "Citation audits: $($citationAudits.Count)"
Write-Host ""
Write-Host "Artifacts:"
Write-Host "- run-state: $RUN_STATE"
Write-Host "- source-rescue: $SOURCE_RESCUE"
Write-Host "- missing-sources: $MISSING_SOURCES"
Write-Host "- candidate-sources: $CANDIDATE_SOURCES"
Write-Host ""
$hasAnyRunArtifact = [bool]($runState -or $rescue -or $candidates -or $sources -or $questions -or (Test-Path -LiteralPath $STATUS))
if (-not $hasAnyRunArtifact) {
    Write-Host "Recommended next state: no run artifacts found" -ForegroundColor Yellow
} elseif ($missingMustHave.Count -gt 0) {
    Write-Host "Recommended next state: NEEDS_SOURCE_RESCUE" -ForegroundColor Yellow
} elseif (-not $questions -or -not $questions.questions -or @($questions.questions | Where-Object { $_.question -and $_.question.Trim().Length -gt 0 }).Count -eq 0) {
    Write-Host "Recommended next state: NEEDS_QUESTIONS" -ForegroundColor Yellow
} elseif ($qaSummaries.Count -eq 0) {
    Write-Host "Recommended next state: resume QA" -ForegroundColor Yellow
} else {
    Write-Host "Recommended next state: inspect QA summaries/citation audit" -ForegroundColor Green
}
Write-Host "Resume command:"
Write-Host (Get-ResumeCommand -RunState $runState -NotebookId $notebookId)
