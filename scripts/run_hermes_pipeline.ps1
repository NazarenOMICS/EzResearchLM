<#
.SYNOPSIS
    Hermes NotebookLM-first pipeline for a confirmed new research corpus.

.DESCRIPTION
    Role split:
    - gpt-5.4 main agent decides strategy and final synthesis.
    - gpt-5.4-mini cheap subagent writes/curates queries, questions, and audits.
    - This script only executes mechanics after queries/questions are provided.

    Non-interactive wrapper. Use this instead of manual search/upload/import steps.
    It searches/downloads papers, creates a NotebookLM notebook, uploads PDFs,
    exports source IDs, imports sources to the vault, runs NotebookLM QA, and
    updates QMD.

    If questions are missing, the script stops with NEEDS_QUESTIONS and leaves
    a gpt-5.4-mini subagent prompt plus a resumable command.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Slug,

    [Parameter(Mandatory = $true)]
    [string]$Goal,

    [Parameter(Mandatory = $true)]
    [string]$QueriesFile,

    [Parameter(Mandatory = $true)]
    [string]$NotebookTitle,

    [Parameter(Mandatory = $true)]
    [string]$Dashboard,

    [string]$Project,
    [string]$VaultSlug,
    [string]$SaveDir,
    [string]$Sources = "pubmed,europepmc,openalex,semantic,crossref",
    [int]$TopN = 5,
    [int]$Workers = 4,
    [int]$QuestionCount = 15,
    [string]$BlockSummaryTitle,
    [switch]$MinOa,
    [switch]$SkipSearch,
    [switch]$SkipGuides,
    [switch]$SkipBatch,
    [switch]$FromExistingQuestions,
    [string]$ExistingNotebookId,
    [string]$MustHaveFile,
    [switch]$AllowAnnaFallback,
    [switch]$StopIfMissingMustHave,
    [string]$ResumeState
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

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
$VAULT = if ($env:EZRESEARCH_VAULT) { $env:EZRESEARCH_VAULT } else { $EZRESEARCH_ROOT }
$pythonCandidates = @(
    $env:EZRESEARCH_PYTHON,
    (Join-Path $EZRESEARCH_ROOT ".venv\Scripts\python.exe"),
    (Join-Path $EZRESEARCH_ROOT ".pdfenv\.venv\Scripts\python.exe"),
    "python"
) | Where-Object { $_ }
$VENV_PY = @($pythonCandidates | Where-Object { $_ -eq "python" -or (Test-Path -LiteralPath $_) } | Select-Object -First 1)[0]
$UVPY = $VENV_PY
$SCRIPTS = Join-Path $EZRESEARCH_ROOT "notebooklm\scripts"
$SEARCH_ROOT = Join-Path $EZRESEARCH_ROOT "Search"
$UPLOADER = Join-Path $EZRESEARCH_ROOT "scripts\upload_sources_parallel.ps1"
$SEARCH_WRAPPER = Join-Path $EZRESEARCH_ROOT "scripts\run_search_topic.ps1"
$paperSearchPath = Join-Path $EZRESEARCH_ROOT "packages\paper_search"
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$paperSearchPath;$env:PYTHONPATH" } else { $paperSearchPath }
$FAILED_UPLOAD_NAMES = @()

function Convert-ToHermesSlug {
    param([string]$Text, [string]$Fallback = "general")
    if (-not $Text) { return $Fallback }
    $normalized = $Text.ToLowerInvariant().Normalize([Text.NormalizationForm]::FormD)
    $chars = foreach ($ch in $normalized.ToCharArray()) {
        if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($ch) -ne [Globalization.UnicodeCategory]::NonSpacingMark) { $ch }
    }
    $ascii = -join $chars
    $slugText = [regex]::Replace($ascii, "[^a-z0-9]+", "-").Trim("-")
    if (-not $slugText) { return $Fallback }
    return $slugText
}

function Resolve-HermesProject {
    param([string]$ExplicitProject, [string]$Text)
    if ($ExplicitProject) { return Convert-ToHermesSlug $ExplicitProject "general" }
    $haystack = ($Text | Out-String).ToLowerInvariant()
    if ($haystack -match "smoke|debug|dry-run|dry run|test run|prueba") { return "smoke-runs" }
    if ($haystack -match "thesis|dissertation|chapter") { return "thesis" }
    if ($haystack -match "proteomic|proteomica|protein|peptid|tryptic|triptic|qubit|lc-ms|lcms|mass spectrometry|espectrometr") { return "proteomics" }
    if ($haystack -match "food|alimento|nutrition|nutricion|diet|dieta|yerba|mate|metabol") { return "alimentos" }
    if ($haystack -match "sleep|sueno|sueño|memory|memoria|rem") { return "neuro-sleep" }
    return "general"
}

$PROJECT = Resolve-HermesProject -ExplicitProject $Project -Text "$Slug $Goal $NotebookTitle $Dashboard"
if ($VaultSlug) {
    $VAULT_SLUG = ($VaultSlug -replace "\\", "/").Trim("/")
} else {
    $VAULT_SLUG = "$PROJECT/$Slug"
}
$RUN_ROOT = Join-Path (Join-Path $AUTORESEARCH "runs") $PROJECT
$RUN_DIR = Join-Path $RUN_ROOT $Slug
$LEGACY_RUN_DIR = Join-Path (Join-Path $AUTORESEARCH "runs") $Slug
if (-not $Project -and $FromExistingQuestions -and (Test-Path -LiteralPath (Join-Path $LEGACY_RUN_DIR "questions-$Slug.json")) -and -not (Test-Path -LiteralPath (Join-Path $RUN_DIR "questions-$Slug.json"))) {
    $PROJECT = "legacy"
    $VAULT_SLUG = $Slug
    $RUN_DIR = $LEGACY_RUN_DIR
}
$QUESTIONS_FILE = Join-Path $RUN_DIR "questions-$Slug.json"
$TMP_SOURCES = Join-Path $RUN_DIR "tmp-sources-$Slug.json"
$PDF_LIST = Join-Path $RUN_DIR "pdf-list-$Slug.txt"
$UPLOAD_LOG = Join-Path $RUN_DIR "upload-log-$Slug.txt"
$STATUS = Join-Path $RUN_DIR "STATUS.md"
$QUESTION_PLANNER_PROMPT = Join-Path $RUN_DIR "subagent-question-planner-prompt.md"
$RUN_STATE = Join-Path $RUN_DIR "run-state.json"
$RUN_CANDIDATE_SOURCES = Join-Path $RUN_DIR "candidate-sources.json"
$RUN_SOURCE_RESCUE = Join-Path $RUN_DIR "source-rescue.json"
$RUN_MISSING_SOURCES = Join-Path $RUN_DIR "missing-sources.md"

if (-not $SaveDir) {
    $SaveDir = Join-Path (Join-Path $SEARCH_ROOT $PROJECT) "$Slug-papers"
}
if (-not $BlockSummaryTitle) {
    $BlockSummaryTitle = "$Dashboard - NotebookLM block summary"
}

function Step {
    param([string]$Name)
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    Add-Content -Path $STATUS -Value "`n## $Name`n"
}

function Note {
    param([string]$Text)
    Write-Host $Text
    Add-Content -Path $STATUS -Value "- $Text"
}

function Get-CurrentNotebookId {
    if (Get-Variable -Name NOTEBOOK_ID -Scope Script -ErrorAction SilentlyContinue) {
        return $script:NOTEBOOK_ID
    }
    return $RESUME_NOTEBOOK_ID
}

function Get-HermesResumeCommand {
    param([string]$NotebookId = "")
    $parts = @(
        "powershell.exe -ExecutionPolicy Bypass -File `"$PSCommandPath`"",
        "-Slug `"$Slug`"",
        "-Project `"$PROJECT`"",
        "-VaultSlug `"$VAULT_SLUG`"",
        "-Goal `"$Goal`"",
        "-QueriesFile `"$QueriesFile`"",
        "-NotebookTitle `"$NotebookTitle`"",
        "-Dashboard `"$Dashboard`"",
        "-SaveDir `"$SaveDir`""
    )
    if ($MustHaveFile) { $parts += "-MustHaveFile `"$MustHaveFile`"" }
    if ($AllowAnnaFallback) { $parts += "-AllowAnnaFallback" }
    if ($StopIfMissingMustHave) { $parts += "-StopIfMissingMustHave" }
    if ($NotebookId) {
        $parts += "-SkipSearch"
        $parts += "-FromExistingQuestions"
        $parts += "-ExistingNotebookId `"$NotebookId`""
    }
    return ($parts -join " ")
}

function Write-RunState {
    param(
        [string]$Stage,
        [string]$StateStatus,
        [hashtable]$Details = @{}
    )
    $stateNotebookId = Get-CurrentNotebookId
    $payload = [ordered]@{
        slug = $Slug
        project = $PROJECT
        vault_slug = $VAULT_SLUG
        goal = $Goal
        stage = $Stage
        status = $StateStatus
        updated_at = (Get-Date -Format s)
        run_dir = $RUN_DIR
        save_dir = $SaveDir
        queries_file = $QueriesFile
        questions_file = $QUESTIONS_FILE
        notebook_id = $stateNotebookId
        tmp_sources = $TMP_SOURCES
        source_rescue = $RUN_SOURCE_RESCUE
        candidate_sources = $RUN_CANDIDATE_SOURCES
        missing_sources = $RUN_MISSING_SOURCES
        must_have_file = $MustHaveFile
        allow_anna_fallback = [bool]$AllowAnnaFallback
        stop_if_missing_must_have = [bool]$StopIfMissingMustHave
        resume_state = $ResumeState
        resume_command = (Get-HermesResumeCommand -NotebookId $stateNotebookId)
        details = $Details
    }
    $payload | ConvertTo-Json -Depth 20 | Set-Content -Path $RUN_STATE -Encoding utf8
}

function Fail {
    param([string]$Text, [int]$Code = 1)
    Write-Host "[FAIL] $Text" -ForegroundColor Red
    Add-Content -Path $STATUS -Value "- FAIL: $Text"
    Write-RunState -Stage "failed" -StateStatus "failed" -Details @{ reason = $Text; exit_code = $Code }
    exit $Code
}

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )
    Write-Host "[$Label]"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Fail "$Label failed with exit code $LASTEXITCODE"
    }
}

function Get-FilledQuestionCount {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    try {
        $payload = Get-Content -LiteralPath $Path -Raw -Encoding utf8 | ConvertFrom-Json
    } catch {
        return 0
    }
    if (-not $payload.questions) { return 0 }
    return @($payload.questions | Where-Object {
        $_.question -and
        $_.question.Trim().Length -gt 0 -and
        $_.question -notmatch "focused NotebookLM question|REPLACE_WITH"
    }).Count
}

function Get-FailedUploadNames {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    return @(Get-Content -LiteralPath $Path -Encoding utf8 | ForEach-Object {
        $m = [regex]::Match($_, "FAIL\s+-\s+(.+\.pdf)\s*$")
        if ($m.Success) { $m.Groups[1].Value.Trim() }
    } | Where-Object { $_ })
}

function Get-NotebookSourcesJson {
    param([string]$NotebookId)

    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $raw = & notebooklm source list --notebook $NotebookId --json 2>&1
    $sourceListExitCode = $LASTEXITCODE
    $ErrorActionPreference = $oldErrorActionPreference
    if ($sourceListExitCode -ne 0) {
        Fail "notebooklm source list failed: $($raw | Out-String)"
    }

    $text = ($raw | Out-String)
    $start = $text.IndexOf("{")
    $end = $text.LastIndexOf("}")
    if ($start -lt 0 -or $end -le $start) {
        Fail "notebooklm source list did not include a JSON object"
    }

    try {
        $payload = $text.Substring($start, $end - $start + 1) | ConvertFrom-Json
    } catch {
        Fail "Could not parse notebooklm source list JSON"
    }

    if ($payload -is [array]) { return @($payload) }
    if ($payload.sources) { return @($payload.sources) }
    if ($payload.items) { return @($payload.items) }
    return @()
}

function Remove-NotebookSourcesByTitle {
    param([string]$NotebookId, [string[]]$Titles)
    if (-not $Titles -or $Titles.Count -eq 0) { return 0 }

    $titleSet = @{}
    foreach ($title in $Titles) { $titleSet[$title.ToLowerInvariant()] = $true }

    $removed = 0
    foreach ($source in @(Get-NotebookSourcesJson $NotebookId)) {
        $title = if ($source.title) { [string]$source.title } elseif ($source.name) { [string]$source.name } else { "" }
        $id = if ($source.id) { [string]$source.id } elseif ($source.source_id) { [string]$source.source_id } else { "" }
        if ($title -and $id -and $titleSet.ContainsKey($title.ToLowerInvariant())) {
            $deleteOutput = & notebooklm source delete --notebook $NotebookId $id -y 2>&1
            if ($LASTEXITCODE -eq 0) {
                $removed++
                Note "Dropped failed upload source from notebook: $title"
            } else {
                Note "WARN could not drop failed upload source: $title :: $($deleteOutput | Out-String)"
            }
        }
    }
    return $removed
}

function Remove-NotebookSourcesByStatus {
    param([string]$NotebookId, [string]$StatusPattern = "error|failed")
    $removed = 0
    foreach ($source in @(Get-NotebookSourcesJson $NotebookId)) {
        $status = ""
        foreach ($field in @("status", "Status", "state", "State")) {
            if ($source.PSObject.Properties.Name -contains $field) {
                $status = [string]$source.$field
                break
            }
        }
        if (-not $status -or $status.ToLowerInvariant() -notmatch $StatusPattern) { continue }
        $title = if ($source.title) { [string]$source.title } elseif ($source.name) { [string]$source.name } else { "" }
        $id = if ($source.id) { [string]$source.id } elseif ($source.source_id) { [string]$source.source_id } else { "" }
        if ($id) {
            $deleteOutput = & notebooklm source delete --notebook $NotebookId $id -y 2>&1
            if ($LASTEXITCODE -eq 0) {
                $removed++
                Note "Dropped NotebookLM errored source: $title [$status]"
            } else {
                Note "WARN could not drop errored source: $title [$status] :: $($deleteOutput | Out-String)"
            }
        }
    }
    return $removed
}

function Get-NotebookIdFromText {
    param([object[]]$Lines)
    $text = ($Lines | Out-String)
    $match = [regex]::Match($text, "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    if ($match.Success) { return $match.Value }
    return ""
}

function Get-NotebookIdFromStatusText {
    param([string]$Text)
    $match = [regex]::Match(($Text | Out-String), "(?m)^- Notebook ID:\s*([0-9a-fA-F-]{36})\s*$")
    if ($match.Success) { return $match.Groups[1].Value }
    return ""
}

function Get-NotebookIdFromQuestionsFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return "" }
    try {
        $data = Get-Content -LiteralPath $Path -Raw -Encoding utf8 | ConvertFrom-Json
        if ($data.notebook_id -match "^[0-9a-fA-F-]{36}$") {
            return [string]$data.notebook_id
        }
    } catch {
        return ""
    }
    return ""
}

function Ensure-NotebookLM {
    $output = & notebooklm list 2>&1
    if ($LASTEXITCODE -ne 0) {
        $text = ($output | Out-String)
        if ($text -match "Authentication expired|invalid|accounts.google.com") {
            Fail "NotebookLM auth failed. Run: powershell.exe -ExecutionPolicy Bypass -File `"$AUTORESEARCH\scripts\auto_login.ps1`""
        }
        Fail "notebooklm list failed: $text"
    }
}

function Ensure-Qmd {
    Push-Location $VAULT
    try {
        $output = & qmd collection list 2>&1
        if ($LASTEXITCODE -ne 0) {
            Fail "qmd collection list failed from vault: $($output | Out-String)"
        }
    } finally {
        Pop-Location
    }
}

function Assert-NotebookSourcesReady {
    param([string]$NotebookId)
    $sources = @(Get-NotebookSourcesJson $NotebookId)

    if ($sources.Count -eq 0) {
        Fail "NotebookLM readiness check found no sources"
    }

    $unknown = @()
    $notReady = @()
    foreach ($source in $sources) {
        $status = ""
        foreach ($field in @("status", "Status", "state", "State")) {
            if ($source.PSObject.Properties.Name -contains $field) {
                $status = [string]$source.$field
                break
            }
        }
        $title = if ($source.title) { $source.title } elseif ($source.name) { $source.name } else { $source.id }
        if (-not $status) {
            $unknown += $title
        } elseif ($status.ToLowerInvariant() -notmatch "ready|completed|available") {
            $notReady += "$title [$status]"
        }
    }

    if ($unknown.Count -gt 0) {
        Fail "NotebookLM source readiness status missing for: $($unknown -join '; ')"
    }
    if ($notReady.Count -gt 0) {
        Fail "NotebookLM sources not ready: $($notReady -join '; ')"
    }

    Note "NotebookLM sources ready: $($sources.Count)"
}

function Sync-SearchArtifacts {
    foreach ($name in @("candidate-sources.json", "source-rescue.json", "missing-sources.md")) {
        $sourcePath = Join-Path $SaveDir $name
        $targetPath = Join-Path $RUN_DIR $name
        if (Test-Path -LiteralPath $sourcePath) {
            Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
            Note "Synced artifact: $targetPath"
        }
    }
}

function Get-SourceRescuePayload {
    $path = $RUN_SOURCE_RESCUE
    if (-not (Test-Path -LiteralPath $path)) {
        $searchPath = Join-Path $SaveDir "source-rescue.json"
        if (Test-Path -LiteralPath $searchPath) { $path = $searchPath }
    }
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try {
        return Get-Content -LiteralPath $path -Raw -Encoding utf8 | ConvertFrom-Json
    } catch {
        Fail "Could not parse source rescue queue: $path"
    }
}

function Get-MissingRequiredSources {
    $payload = Get-SourceRescuePayload
    if (-not $payload -or -not $payload.sources) { return @() }
    return @($payload.sources | Where-Object {
        $_.required -eq $true -and $_.status -notin @("downloaded", "notebook_ready")
    })
}

function Get-ObjectPropertyValue {
    param([object]$Object, [string[]]$Names)
    foreach ($name in $Names) {
        if ($Object.PSObject.Properties.Name -contains $name) {
            $value = [string]$Object.$name
            if ($value) { return $value }
        }
    }
    return ""
}

function Convert-ToMatchKey {
    param([string]$Text)
    return ([regex]::Replace(($Text | Out-String).ToLowerInvariant(), "[^a-z0-9]+", "")).Trim()
}

function Update-SourceRescueNotebookStatus {
    param([string]$NotebookId)
    if (-not (Test-Path -LiteralPath $RUN_SOURCE_RESCUE)) { return }
    if (-not (Test-Path -LiteralPath $TMP_SOURCES)) { return }
    try {
        $rescue = Get-Content -LiteralPath $RUN_SOURCE_RESCUE -Raw -Encoding utf8 | ConvertFrom-Json
        $sourcePayload = Get-Content -LiteralPath $TMP_SOURCES -Raw -Encoding utf8 | ConvertFrom-Json
    } catch {
        Note "WARN could not update source-rescue notebook status"
        return
    }
    $notebookSources = @()
    if ($sourcePayload -is [array]) {
        $notebookSources = @($sourcePayload)
    } elseif ($sourcePayload.sources) {
        $notebookSources = @($sourcePayload.sources)
    } elseif ($sourcePayload.items) {
        $notebookSources = @($sourcePayload.items)
    }

    $changed = $false
    foreach ($entry in @($rescue.sources)) {
        if (-not $entry.pdf_path) { continue }
        if ($entry.status -notin @("downloaded", "notebook_ready")) { continue }
        $fileStem = Convert-ToMatchKey ([IO.Path]::GetFileNameWithoutExtension([string]$entry.pdf_path))
        $titleKey = Convert-ToMatchKey ([string]$entry.title)
        foreach ($source in $notebookSources) {
            $sourceText = @(
                (Get-ObjectPropertyValue $source @("title", "name", "source_title", "display_name")),
                (Get-ObjectPropertyValue $source @("file_name", "filename", "path"))
            ) -join " "
            $sourceKey = Convert-ToMatchKey $sourceText
            if (($fileStem -and $sourceKey -and ($sourceKey.Contains($fileStem) -or $fileStem.Contains($sourceKey))) -or
                ($titleKey -and $sourceKey -and ($sourceKey.Contains($titleKey) -or $titleKey.Contains($sourceKey)))) {
                $sourceId = Get-ObjectPropertyValue $source @("id", "source_id", "sourceId")
                if ($sourceId) {
                    $entry.notebook_source_id = $sourceId
                    $entry.status = "notebook_ready"
                    $entry.failure_reason = $null
                    $changed = $true
                }
                break
            }
        }
    }
    if ($changed) {
        $rescue | ConvertTo-Json -Depth 20 | Set-Content -Path $RUN_SOURCE_RESCUE -Encoding utf8
        Note "Source rescue updated with NotebookLM source IDs"
    }
}

New-Item -ItemType Directory -Force -Path $RUN_DIR | Out-Null
$PREVIOUS_STATUS_TEXT = ""
if (Test-Path -LiteralPath $STATUS) {
    $PREVIOUS_STATUS_TEXT = Get-Content -LiteralPath $STATUS -Raw -Encoding utf8
}
$RESUME_NOTEBOOK_ID = $ExistingNotebookId
if (-not $RESUME_NOTEBOOK_ID -and $ResumeState -and (Test-Path -LiteralPath $ResumeState)) {
    try {
        $resumePayload = Get-Content -LiteralPath $ResumeState -Raw -Encoding utf8 | ConvertFrom-Json
        if ($resumePayload.notebook_id -match "^[0-9a-fA-F-]{36}$") {
            $RESUME_NOTEBOOK_ID = [string]$resumePayload.notebook_id
        }
    } catch {
        # ResumeState is advisory; normal validation below will report required inputs.
    }
}
if (-not $RESUME_NOTEBOOK_ID -and $FromExistingQuestions) {
    $RESUME_NOTEBOOK_ID = Get-NotebookIdFromQuestionsFile $QUESTIONS_FILE
}
if (-not $RESUME_NOTEBOOK_ID -and $FromExistingQuestions) {
    $RESUME_NOTEBOOK_ID = Get-NotebookIdFromStatusText $PREVIOUS_STATUS_TEXT
}

Set-Content -Path $STATUS -Encoding utf8 -Value @"
# STATUS - $Slug

Started: $(Get-Date -Format s)
Goal: $Goal
Notebook title: $NotebookTitle
Dashboard: $Dashboard
Project: $PROJECT
Vault slug: $VAULT_SLUG
Queries file: $QueriesFile
Papers dir: $SaveDir
Resume notebook: $RESUME_NOTEBOOK_ID
Must-have file: $MustHaveFile
Allow Anna fallback: $([bool]$AllowAnnaFallback)
Stop if missing must-have: $([bool]$StopIfMissingMustHave)
Resume state: $ResumeState
"@
Write-RunState -Stage "initialized" -StateStatus "running"

if ($FromExistingQuestions -and (Get-FilledQuestionCount $QUESTIONS_FILE) -eq 0) {
    Add-Content -Path $STATUS -Value "`n## NEEDS_QUESTIONS`n- Reason: -FromExistingQuestions was passed but no filled questions file exists.`n- Questions file: $QUESTIONS_FILE"
    Write-RunState -Stage "questions" -StateStatus "needs_questions" -Details @{ reason = "resume_without_filled_questions" }
    Write-Host "NEEDS_QUESTIONS" -ForegroundColor Yellow
    Write-Host "-FromExistingQuestions is resume-only. Fill questions first, or rerun without -FromExistingQuestions to create/import corpus and stop at NEEDS_QUESTIONS."
    Write-Host "Questions file: $QUESTIONS_FILE"
    exit 2
}
if ($FromExistingQuestions -and -not $RESUME_NOTEBOOK_ID) {
    Add-Content -Path $STATUS -Value "`n## NEEDS_NOTEBOOK_ID`n- Reason: -FromExistingQuestions was passed but no existing Notebook ID was found.`n- Fix: pass -ExistingNotebookId or rerun initial corpus without -FromExistingQuestions."
    Write-RunState -Stage "notebook" -StateStatus "needs_notebook_id"
    Write-Host "NEEDS_NOTEBOOK_ID" -ForegroundColor Yellow
    Write-Host "-FromExistingQuestions is resume-only and needs an existing NotebookLM notebook."
    Write-Host "Pass -ExistingNotebookId, or rerun without -FromExistingQuestions to create/import corpus first."
    exit 2
}

Step "0 Preflight"
if (-not (Test-Path $VENV_PY)) { Fail "Python venv not found: $VENV_PY" }
if (-not (Test-Path $UVPY)) { Fail "NotebookLM uv Python not found: $UVPY" }
if (-not (Test-Path $QueriesFile)) { Fail "QueriesFile not found: $QueriesFile" }
Ensure-NotebookLM
Ensure-Qmd
Note "NotebookLM list OK"
Note "QMD collection list OK"
Note "Project: $PROJECT"
Note "Vault slug: $VAULT_SLUG"
Write-RunState -Stage "preflight" -StateStatus "ok"

Step "1 Search and download"
New-Item -ItemType Directory -Force -Path $SaveDir | Out-Null
if (-not $SkipSearch) {
    $searchArgs = @(
        "-ExecutionPolicy", "Bypass",
        "-File", $SEARCH_WRAPPER,
        "-Slug", $Slug,
        "-QueriesFile", $QueriesFile,
        "-SaveDir", $SaveDir,
        "-Sources", $Sources,
        "-TopN", $TopN.ToString()
    )
    if ($MinOa) { $searchArgs += "-MinOa" }
    if ($MustHaveFile) { $searchArgs += @("-MustHaveFile", $MustHaveFile) }
    if ($AllowAnnaFallback) { $searchArgs += "-AllowAnnaFallback" }
    & powershell.exe @searchArgs
    if ($LASTEXITCODE -ne 0) { Fail "search wrapper failed" }
} else {
    Note "SkipSearch set; using existing PDFs in $SaveDir"
}
Sync-SearchArtifacts
$missingRequired = @(Get-MissingRequiredSources)
if ($missingRequired.Count -gt 0) {
    Add-Content -Path $STATUS -Value "`n## NEEDS_SOURCE_RESCUE`n- Missing required sources: $($missingRequired.Count)`n- Source rescue: $RUN_SOURCE_RESCUE`n- Missing sources: $RUN_MISSING_SOURCES"
    foreach ($missing in $missingRequired) {
        Add-Content -Path $STATUS -Value "- `$($missing.target_id)` $($missing.title) :: $($missing.failure_reason)"
    }
    Write-RunState -Stage "source_rescue" -StateStatus "needs_source_rescue" -Details @{ missing_required = $missingRequired.Count; source_rescue = $RUN_SOURCE_RESCUE; missing_sources = $RUN_MISSING_SOURCES }
    Write-Host "NEEDS_SOURCE_RESCUE" -ForegroundColor Yellow
    Write-Host "Missing required sources: $($missingRequired.Count)"
    Write-Host "Source rescue: $RUN_SOURCE_RESCUE"
    Write-Host "Missing sources: $RUN_MISSING_SOURCES"
    Write-Host "Run doctor:"
    Write-Host "powershell.exe -ExecutionPolicy Bypass -File `"$AUTORESEARCH\scripts\run_hermes_doctor.ps1`" -Project `"$PROJECT`" -Slug `"$Slug`""
    exit 2
}
$pdfs = @(Get-ChildItem -LiteralPath $SaveDir -Filter "*.pdf" -File -ErrorAction SilentlyContinue)
if ($pdfs.Count -eq 0) { Fail "No PDFs found in $SaveDir after search" }
Note "PDFs ready: $($pdfs.Count)"
Write-RunState -Stage "search" -StateStatus "ok" -Details @{ pdf_count = $pdfs.Count; missing_required = $missingRequired.Count }

if ($RESUME_NOTEBOOK_ID) {
    Step "2 Reuse NotebookLM notebook"
    $NOTEBOOK_ID = $RESUME_NOTEBOOK_ID
    Note "Notebook ID: $NOTEBOOK_ID"
    Note "ExistingNotebookId set: notebook creation skipped"
    Write-RunState -Stage "notebook" -StateStatus "reused"
} else {
    Step "2 Create NotebookLM notebook"
    $createOutput = & notebooklm create $NotebookTitle 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "notebooklm create failed: $($createOutput | Out-String)" }
    $NOTEBOOK_ID = Get-NotebookIdFromText $createOutput
    if (-not $NOTEBOOK_ID) { Fail "Could not parse notebook ID from notebooklm create output" }
    Note "Notebook ID: $NOTEBOOK_ID"
    Write-RunState -Stage "notebook" -StateStatus "created"
}

if ($RESUME_NOTEBOOK_ID) {
    Step "3 Reuse uploaded PDFs"
    $FAILED_UPLOAD_NAMES = @(Get-FailedUploadNames $UPLOAD_LOG)
    if ($FAILED_UPLOAD_NAMES.Count -gt 0) {
        Note "Previous upload failures found: $($FAILED_UPLOAD_NAMES.Count)"
    }
    Note "ExistingNotebookId set: upload skipped"
} else {
    Step "3 Upload PDFs"
    $pdfs | ForEach-Object { $_.Name } | Set-Content -Path $PDF_LIST -Encoding utf8
    & $UPLOADER -NotebookId $NOTEBOOK_ID -PdfsDir $SaveDir -PdfList $PDF_LIST -Workers $Workers -LogFile $UPLOAD_LOG
    $uploadExit = $LASTEXITCODE
    $FAILED_UPLOAD_NAMES = @(Get-FailedUploadNames $UPLOAD_LOG)
    if ($uploadExit -ne 0 -and $FAILED_UPLOAD_NAMES.Count -eq 0) {
        Fail "parallel upload failed; see $UPLOAD_LOG"
    }
    if ($uploadExit -ne 0 -or $FAILED_UPLOAD_NAMES.Count -gt 0) {
        $okCount = [Math]::Max(0, ($pdfs.Count - $FAILED_UPLOAD_NAMES.Count))
        if ($okCount -le 0) { Fail "parallel upload failed for all PDFs; see $UPLOAD_LOG" }
        Note "Upload had failures: $($FAILED_UPLOAD_NAMES.Count). Continuing with $okCount uploaded PDFs."
    }
    Note "Upload log: $UPLOAD_LOG"
}
Write-RunState -Stage "upload" -StateStatus "ok" -Details @{ failed_uploads = $FAILED_UPLOAD_NAMES.Count }

Step "4 Export NotebookLM sources"
& $UVPY (Join-Path $SCRIPTS "list_sources_to_json.py") `
    --notebook $NOTEBOOK_ID `
    --out $TMP_SOURCES `
    --title $NotebookTitle
if ($LASTEXITCODE -ne 0) { Fail "list_sources_to_json.py failed" }
if (-not (Test-Path $TMP_SOURCES)) { Fail "sources JSON not created: $TMP_SOURCES" }
Note "Sources JSON: $TMP_SOURCES"
if ($FAILED_UPLOAD_NAMES.Count -gt 0) {
    $removed = Remove-NotebookSourcesByTitle -NotebookId $NOTEBOOK_ID -Titles $FAILED_UPLOAD_NAMES
    if ($removed -gt 0) {
        & $UVPY (Join-Path $SCRIPTS "list_sources_to_json.py") `
            --notebook $NOTEBOOK_ID `
            --out $TMP_SOURCES `
            --title $NotebookTitle
        if ($LASTEXITCODE -ne 0) { Fail "list_sources_to_json.py failed after dropping failed uploads" }
        Note "Sources JSON refreshed after dropping failed uploads"
    }
}
$removedErrored = Remove-NotebookSourcesByStatus -NotebookId $NOTEBOOK_ID
if ($removedErrored -gt 0) {
    & $UVPY (Join-Path $SCRIPTS "list_sources_to_json.py") `
        --notebook $NOTEBOOK_ID `
        --out $TMP_SOURCES `
        --title $NotebookTitle
    if ($LASTEXITCODE -ne 0) { Fail "list_sources_to_json.py failed after dropping errored sources" }
    Note "Sources JSON refreshed after dropping errored sources"
}
Assert-NotebookSourcesReady $NOTEBOOK_ID
Update-SourceRescueNotebookStatus -NotebookId $NOTEBOOK_ID
Write-RunState -Stage "sources" -StateStatus "ready"

$SOURCE_NOTES_DIR = Join-Path (Join-Path (Join-Path $VAULT "Notes") "NotebookLM") (Join-Path $VAULT_SLUG "Sources")
$existingSourceNotes = if (Test-Path -LiteralPath $SOURCE_NOTES_DIR) {
    @(Get-ChildItem -LiteralPath $SOURCE_NOTES_DIR -Filter "*.md" -File -ErrorAction SilentlyContinue)
} else {
    @()
}

if ($FromExistingQuestions -and $RESUME_NOTEBOOK_ID -and $existingSourceNotes.Count -gt 0) {
    Step "5 Reuse imported sources"
    Note "Resume mode: source import skipped; existing source notes: $($existingSourceNotes.Count)"
} else {
    Step "5 Import sources to vault"
    if ($FromExistingQuestions -and $RESUME_NOTEBOOK_ID) {
        Note "Resume mode but source notes missing; importing sources to vault"
    }
    Push-Location $VAULT
    try {
        $importArgs = @(
            (Join-Path $SCRIPTS "import_sources.py"),
            "--sources", $TMP_SOURCES,
            "--slug", $Slug,
            "--vault-slug", $VAULT_SLUG,
            "--project", $PROJECT,
            "--papers-vault-subdir", "Research/Papers/$VAULT_SLUG",
            "--dashboard", $Dashboard,
            "--papers-dir", $SaveDir
        )
        if ($SkipGuides) { $importArgs += "--skip-guides" }
        & $VENV_PY @importArgs
        if ($LASTEXITCODE -ne 0) { Fail "import_sources.py failed" }
    } finally {
        Pop-Location
    }
    Note "Sources imported to vault"
}
Write-RunState -Stage "import" -StateStatus "ok"

Step "6 Prepare subagent questions"
if (-not $FromExistingQuestions) {
    Note "NEEDS_QUESTIONS: questions are owned by gpt-5.4-mini. Fill $QUESTIONS_FILE with subagent-curated questions, then rerun with -FromExistingQuestions -SkipSearch -ExistingNotebookId $NOTEBOOK_ID."
    Set-Content -Path $QUESTION_PLANNER_PROMPT -Encoding utf8 -Value @"
# NotebookLM Question Planner Subagent Task

Use model: gpt-5.4-mini.

Return JSON only. Do not run tools. Do not answer the questions.

Input JSON:

{
  "slug": "$Slug",
  "project": "$PROJECT",
  "vault_slug": "$VAULT_SLUG",
  "goal": "$Goal",
  "dashboard": "$Dashboard",
  "notebook_id": "$NOTEBOOK_ID",
  "sources_json": "$TMP_SOURCES"
}

Required output JSON:

{
  "slug": "$Slug",
  "goal": "$Goal",
  "dashboard": "$Dashboard",
  "notebook_id": "$NOTEBOOK_ID",
  "questions": [
    {
      "id": 1,
      "theme": "core-evidence",
      "question": "focused NotebookLM question",
      "status": "pending"
    }
  ]
}

Rules:

- IDs are integers.
- Create 3-8 focused questions for small corpus.
- Cover core evidence, mechanisms/comparisons, limitations/gaps.
- Do not collapse goal into one broad QA.
- Questions must force cited answers from NotebookLM.
"@
    $template = [ordered]@{
        slug = $Slug
        project = $PROJECT
        vault_slug = $VAULT_SLUG
        goal = $Goal
        dashboard = $Dashboard
        notebook_id = $NOTEBOOK_ID
        questions = @(
            [ordered]@{ id = 1; theme = "core-evidence"; question = ""; status = "pending" },
            [ordered]@{ id = 2; theme = "mechanisms"; question = ""; status = "pending" },
            [ordered]@{ id = 3; theme = "limitations"; question = ""; status = "pending" }
        )
    }
    $template | ConvertTo-Json -Depth 20 | Set-Content -Path $QUESTIONS_FILE -Encoding utf8
}
if (-not (Test-Path $QUESTIONS_FILE)) { Fail "Questions file missing: $QUESTIONS_FILE" 2 }

$qData = Get-Content -LiteralPath $QUESTIONS_FILE -Raw -Encoding utf8 | ConvertFrom-Json
if (-not $qData.notebook_id) {
    if ($qData.PSObject.Properties.Name -contains "notebook_id") {
        $qData.notebook_id = $NOTEBOOK_ID
    } else {
        $qData | Add-Member -NotePropertyName "notebook_id" -NotePropertyValue $NOTEBOOK_ID
    }
}
if ($qData.PSObject.Properties.Name -contains "project") {
    $qData.project = $PROJECT
} else {
    $qData | Add-Member -NotePropertyName "project" -NotePropertyValue $PROJECT
}
if ($qData.PSObject.Properties.Name -contains "vault_slug") {
    $qData.vault_slug = $VAULT_SLUG
} else {
    $qData | Add-Member -NotePropertyName "vault_slug" -NotePropertyValue $VAULT_SLUG
}
if ($qData.PSObject.Properties.Name -contains "dashboard") {
    $qData.dashboard = $Dashboard
} else {
    $qData | Add-Member -NotePropertyName "dashboard" -NotePropertyValue $Dashboard
}
$qData | ConvertTo-Json -Depth 20 | Set-Content -Path $QUESTIONS_FILE -Encoding utf8

$filled = @($qData.questions | Where-Object { $_.question -and $_.question.Trim().Length -gt 0 })
if ($filled.Count -eq 0) {
    Note "NEEDS_QUESTIONS: fill $QUESTIONS_FILE, then rerun with -FromExistingQuestions -SkipSearch -ExistingNotebookId $NOTEBOOK_ID"
    Write-RunState -Stage "questions" -StateStatus "needs_questions" -Details @{ questions_file = $QUESTIONS_FILE; subagent_prompt = $QUESTION_PLANNER_PROMPT }
    Write-Host "NEEDS_QUESTIONS" -ForegroundColor Yellow
    Write-Host "Fill: $QUESTIONS_FILE"
    Write-Host "Subagent prompt: $QUESTION_PLANNER_PROMPT"
    Write-Host "Use gpt-5.4-mini to write focused questions. Do not use one broad prompt as one QA."
    Write-Host "Resume:"
    Write-Host "powershell.exe -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Slug `"$Slug`" -Project `"$PROJECT`" -VaultSlug `"$VAULT_SLUG`" -Goal `"$Goal`" -QueriesFile `"$QueriesFile`" -NotebookTitle `"$NotebookTitle`" -Dashboard `"$Dashboard`" -SaveDir `"$SaveDir`" -SkipSearch -FromExistingQuestions -ExistingNotebookId `"$NOTEBOOK_ID`""
    exit 2
}
Note "Filled questions: $($filled.Count)"
Write-RunState -Stage "questions" -StateStatus "ok" -Details @{ filled_questions = $filled.Count }

$pendingQuestions = @($filled | Where-Object { $_.status -eq "pending" })
$existingQaFiles = @($filled | Where-Object { $_.qa_file -and (Test-Path -LiteralPath $_.qa_file) })
$BatchFromStep = ""
if ($pendingQuestions.Count -eq 0 -and $existingQaFiles.Count -gt 0) {
    $BatchFromStep = "extract"
    Note "No pending questions; reusing existing QA files from batch step: $BatchFromStep"
}

if ($SkipBatch) {
    Note "SkipBatch set; stopping before NotebookLM QA"
    Write-RunState -Stage "qa" -StateStatus "skipped"
    exit 0
}

Step "7 NotebookLM QA export"
Push-Location $VAULT
try {
    $batchArgs = @(
        (Join-Path $SCRIPTS "batch_ask.py"),
        "--questions", $QUESTIONS_FILE,
        "--sources", $TMP_SOURCES,
        "--notebook-id", $NOTEBOOK_ID,
        "--tmp-dir", $RUN_DIR,
        "--block-summary-title", $BlockSummaryTitle
    )
    if ($BatchFromStep) {
        $batchArgs += @("--from-step", $BatchFromStep)
    }
    & $VENV_PY @batchArgs
    if ($LASTEXITCODE -ne 0) { Fail "batch_ask.py failed" }
} finally {
    Pop-Location
}
Note "QA exported"
Write-RunState -Stage "qa" -StateStatus "ok"

Step "8 QMD update"
Push-Location $VAULT
try {
    & qmd update
    if ($LASTEXITCODE -ne 0) { Fail "qmd update failed" }
} finally {
    Pop-Location
}
Note "QMD updated"
Note "Done: $VAULT\Notes\NotebookLM\$VAULT_SLUG"
Write-RunState -Stage "done" -StateStatus "ok"
