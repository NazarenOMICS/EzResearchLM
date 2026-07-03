<#
.SYNOPSIS
    NotebookLM-first answer wrapper for one substantive question.

.DESCRIPTION
    Role split:
    - gpt-5.4 main agent decides strategy and final synthesis.
    - gpt-5.4-mini cheap subagent writes/curates corpus queries.
    - This script only screens QMD, writes run scaffolding, and executes
      NotebookLM mechanics when enough corpus already exists.

    QMD screens existing vault corpus. If enough source evidence exists, this
    creates a fresh NotebookLM notebook for the question, uploads recoverable
    PDFs/URLs from source notes, runs NotebookLM QA, exports citations to the
    vault, and prints the summary paths.

    If evidence is insufficient, it emits NEEDS_CORPUS and a suggested queries
    placeholder plus a subagent prompt. It does not answer from memory.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Question,

    [ValidateSet("answer", "thesis")]
    [string]$Mode = "answer",

    [int]$TopN = 8,
    [int]$MinSources = 3,
    [int]$MinScore = 15,
    [int]$Workers = 4,
    [string]$Slug,
    [string]$Dashboard,
    [switch]$NoExpandQueries,
    [switch]$FromExistingQuestions
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
$SCRIPTS = Join-Path $EZRESEARCH_ROOT "notebooklm\scripts"
$UPLOADER = Join-Path $EZRESEARCH_ROOT "scripts\upload_sources_parallel.ps1"
$paperSearchPath = Join-Path $EZRESEARCH_ROOT "packages\paper_search"
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$paperSearchPath;$env:PYTHONPATH" } else { $paperSearchPath }

function Convert-ToSlug {
    param([string]$Text, [int]$MaxWords = 8)
    $normalized = $Text.ToLowerInvariant().Normalize([Text.NormalizationForm]::FormD)
    $chars = foreach ($ch in $normalized.ToCharArray()) {
        if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($ch) -ne [Globalization.UnicodeCategory]::NonSpacingMark) { $ch }
    }
    $ascii = -join $chars
    $words = [regex]::Matches($ascii, "[a-z0-9]+") | ForEach-Object { $_.Value }
    $skip = @("que","como","cual","cuales","son","las","los","del","con","para","por","una","uno","the","and","for","with","what","how")
    $kept = @($words | Where-Object { $skip -notcontains $_ } | Select-Object -First $MaxWords)
    if ($kept.Count -eq 0) { return "qa-question" }
    return ($kept -join "-")
}

function Fail {
    param([string]$Text, [int]$Code = 1)
    Write-Host "[FAIL] $Text" -ForegroundColor Red
    exit $Code
}

function Get-NotebookIdFromText {
    param([object[]]$Lines)
    $text = ($Lines | Out-String)
    $match = [regex]::Match($text, "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    if ($match.Success) { return $match.Value }
    return ""
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
                Add-Content -Path $STATUS -Value "- Dropped NotebookLM errored source: $title [$status]"
                Write-Host "Dropped NotebookLM errored source: $title [$status]"
            } else {
                Add-Content -Path $STATUS -Value "- WARN could not drop errored source: $title [$status]"
                Write-Host "[WARN] could not drop errored source: $title [$status] :: $($deleteOutput | Out-String)" -ForegroundColor Yellow
            }
        }
    }
    return $removed
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

    Add-Content -Path $STATUS -Value "- NotebookLM sources ready: $($sources.Count)"
    Write-Host "NotebookLM sources ready: $($sources.Count)"
}

function Resolve-QmdPath {
    param([string]$QmdPath)
    $clean = $QmdPath -replace "^qmd://notes/", ""
    $clean = $clean -replace ":\d+$", ""
    if (-not $clean.EndsWith(".md")) { $clean = "$clean.md" }
    if ($clean -match "^(Notes|Hermes)[\\/]") {
        $path = Join-Path $VAULT $clean
    } else {
        $path = Join-Path (Join-Path $VAULT "Notes\NotebookLM") $clean
    }
    if (Test-Path $path) { return $path }
    return $null
}

function Get-CorpusRootFromQmdPath {
    param([string]$QmdPath)
    $clean = $QmdPath -replace "^qmd://notes/", ""
    $clean = $clean -replace ":\d+$", ""
    $parts = @($clean -split "[\\/]" | Where-Object { $_ })
    if ($parts.Count -eq 0) { return $null }

    $slugParts = @($parts[0])
    for ($i = 0; $i -lt $parts.Count - 1; $i++) {
        if ($parts[$i].Equals("NotebookLM", [StringComparison]::OrdinalIgnoreCase)) {
            $slugParts = @()
            for ($j = $i + 1; $j -lt $parts.Count; $j++) {
                if ($parts[$j].Equals("Sources", [StringComparison]::OrdinalIgnoreCase) -or
                    $parts[$j].Equals("QA", [StringComparison]::OrdinalIgnoreCase)) {
                    break
                }
                $slugParts += $parts[$j]
            }
            break
        }
    }

    if ($slugParts.Count -eq 0) { return $null }
    $slug = ($slugParts -join "\")
    $root = Join-Path (Join-Path $VAULT "Notes\NotebookLM") $slug
    if (Test-Path $root) { return $root }
    return $null
}

function Parse-QmdHits {
    param([string[]]$Lines)
    $hits = @()
    $current = $null
    foreach ($line in $Lines) {
        $m = [regex]::Match($line, "^(qmd://[^\s:]+(?:/[^\s:]+)*):?(\d+)?")
        if ($m.Success) {
            if ($current) { $hits += $current }
            $current = [pscustomobject]@{
                Path = $m.Groups[1].Value
                Score = 0
                Snippet = ""
            }
            continue
        }
        if ($null -eq $current) { continue }
        $sm = [regex]::Match($line.Trim(), "^Score:\s+(\d+)%")
        if ($sm.Success) {
            $current.Score = [int]$sm.Groups[1].Value
            continue
        }
        if ($line.Trim().Length -gt 0 -and -not $line.StartsWith("---")) {
            $current.Snippet = ($current.Snippet + " " + $line.Trim()).Trim()
        }
    }
    if ($current) { $hits += $current }
    return @($hits | Sort-Object Score -Descending)
}

function Get-SourceLinksFromSummary {
    param([string]$Path)
    $text = Get-Content -LiteralPath $Path -Raw -Encoding utf8
    $matches = [regex]::Matches($text, "\[\[Notes/NotebookLM/(.+?)/Sources/([^\]#|]+)")
    foreach ($m in $matches) {
        $slug = $m.Groups[1].Value -replace "/", "\"
        $name = $m.Groups[2].Value
        $sourcePath = Join-Path (Join-Path $VAULT "Notes\NotebookLM") (Join-Path $slug "Sources\$name.md")
        if (Test-Path $sourcePath) { $sourcePath }
    }
}

function Get-SourceLinksFromCorpus {
    param([string]$CorpusRoot)
    $paths = New-Object System.Collections.Generic.HashSet[string]
    $summaryDir = Join-Path $CorpusRoot "QA\summaries"
    if (Test-Path $summaryDir) {
        $curationNotes = @(Get-ChildItem -LiteralPath $summaryDir -Filter "*Source Curation.md" -File -ErrorAction SilentlyContinue)
        foreach ($note in $curationNotes) {
            foreach ($src in Get-SourceLinksFromSummary $note.FullName) { [void]$paths.Add($src) }
        }
    }
    if ($paths.Count -eq 0) {
        $sourcesDir = Join-Path $CorpusRoot "Sources"
        if (Test-Path $sourcesDir) {
            Get-ChildItem -LiteralPath $sourcesDir -Filter "*.md" -File -ErrorAction SilentlyContinue |
                ForEach-Object { [void]$paths.Add($_.FullName) }
        }
    }
    return @($paths)
}

function Get-SourceAsset {
    param([string]$SourcePath)
    $text = Get-Content -LiteralPath $SourcePath -TotalCount 80 -Encoding utf8 | Out-String
    $pdf = ""
    $url = ""
    $title = [IO.Path]::GetFileNameWithoutExtension($SourcePath)
    $pm = [regex]::Match($text, '(?m)^pdf:\s+"?([^"\r\n]+)"?')
    if ($pm.Success) {
        $pdfRel = $pm.Groups[1].Value.Trim().Trim('"')
        $candidate = Join-Path $VAULT $pdfRel
        if (Test-Path $candidate) { $pdf = $candidate }
    }
    $um = [regex]::Match($text, '(?m)^url:\s+"?([^"\r\n]+)"?')
    if ($um.Success) {
        $candidateUrl = $um.Groups[1].Value.Trim().Trim('"')
        if ($candidateUrl -match "^https?://") { $url = $candidateUrl }
    }
    if ($pdf -or $url) {
        [pscustomobject]@{ Title = $title; Path = $SourcePath; Pdf = $pdf; Url = $url }
    }
}

if (-not $Slug) { $Slug = "qa-" + (Get-Date -Format "yyyyMMdd") + "-" + (Convert-ToSlug $Question) }
if (-not $Dashboard) { $Dashboard = "Hermes QA - $Slug" }

$RUN_DIR = Join-Path (Join-Path $AUTORESEARCH "runs") $Slug
$STATUS = Join-Path $RUN_DIR "STATUS.md"
$QUESTIONS_FILE = Join-Path $RUN_DIR "questions-$Slug.json"
$TMP_SOURCES = Join-Path $RUN_DIR "tmp-sources-$Slug.json"
$PDF_DIR = Join-Path $RUN_DIR "pdfs"
$PDF_LIST = Join-Path $RUN_DIR "pdf-list-$Slug.txt"
$UPLOAD_LOG = Join-Path $RUN_DIR "upload-log-$Slug.txt"
$QUERIES_FILE = Join-Path $RUN_DIR "queries-$Slug.json"
$CORPUS_PLANNER_PROMPT = Join-Path $RUN_DIR "subagent-corpus-planner-prompt.md"
$QUESTION_PLANNER_PROMPT = Join-Path $RUN_DIR "subagent-question-planner-prompt.md"
$NOTEBOOK_TITLE = "QA $(Get-Date -Format yyyy-MM-dd) - $(Convert-ToSlug $Question 6)"

New-Item -ItemType Directory -Force -Path $RUN_DIR, $PDF_DIR | Out-Null
Set-Content -Path $STATUS -Encoding utf8 -Value @"
# STATUS - $Slug

Started: $(Get-Date -Format s)
Mode: $Mode
Question: $Question
"@

Write-Host "=== QMD recall ===" -ForegroundColor Cyan
Push-Location $VAULT
try {
    $qmdOutput = & qmd search $Question -c notes -n $TopN 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "qmd search failed: $($qmdOutput | Out-String)" }
} finally {
    Pop-Location
}
$allHits = @(Parse-QmdHits $qmdOutput)
foreach ($hit in @($allHits | Select-Object -First ([Math]::Min($TopN, 5)))) {
    $snippet = $hit.Snippet
    if ($snippet.Length -gt 260) { $snippet = $snippet.Substring(0, 260) + "..." }
    Write-Host ("Score {0}% :: {1}" -f $hit.Score, $hit.Path)
    if ($snippet) { Write-Host "  $snippet" }
}
$hits = @($allHits | Where-Object { $_.Score -ge $MinScore })

$sourcePaths = New-Object System.Collections.Generic.HashSet[string]
foreach ($hit in $hits) {
    $file = Resolve-QmdPath $hit.Path
    $corpusRoot = Get-CorpusRootFromQmdPath $hit.Path
    if (-not $file) {
        if ($corpusRoot) {
            foreach ($src in Get-SourceLinksFromCorpus $corpusRoot) { [void]$sourcePaths.Add($src) }
        }
        continue
    }
    if ($file -match "\\Sources\\[^\\]+\.md$") {
        [void]$sourcePaths.Add($file)
    } elseif ($file -match "\\QA\\summaries\\") {
        foreach ($src in Get-SourceLinksFromSummary $file) { [void]$sourcePaths.Add($src) }
    } elseif ($file -match "\\QA\\answers\\") {
        foreach ($src in Get-SourceLinksFromSummary $file) { [void]$sourcePaths.Add($src) }
    }
}

$assets = @($sourcePaths | ForEach-Object { Get-SourceAsset $_ } | Where-Object { $_ })
$uniqueAssets = @()
$seen = New-Object System.Collections.Generic.HashSet[string]
foreach ($asset in $assets) {
    $key = if ($asset.Pdf) { $asset.Pdf } else { $asset.Url }
    if ($key -and $seen.Add($key)) { $uniqueAssets += $asset }
}

if ($uniqueAssets.Count -lt $MinSources) {
    Set-Content -Path $CORPUS_PLANNER_PROMPT -Encoding utf8 -Value @"
# Corpus Planner Subagent Task

Use model: gpt-5.4-mini.

Return JSON only. Do not run tools. Do not answer the research question.

Input JSON:

{
  "slug": "$Slug",
  "goal": "$Question",
  "user_question": "$Question",
  "known_context": "QMD found $($hits.Count) hits above score $MinScore and $($uniqueAssets.Count) recoverable sources. Corpus creation is needed."
}

Required output JSON:

{
  "queries": [
    "6-10 excellent discovery queries for PubMed/EuropePMC/OpenAlex"
  ],
  "rationale": "one short paragraph explaining coverage"
}

Rules:

- English academic terms by default.
- Mix broad review, mechanisms, outcomes, population/context, and methods.
- Avoid vague one-word queries and giant Boolean strings.
- Queries quality controls source quality.
"@
    if ($NoExpandQueries) {
        @($Question) | ConvertTo-Json -Depth 5 | Set-Content -Path $QUERIES_FILE -Encoding utf8
    } else {
        @(
            "REPLACE_WITH_GPT_5_4_MINI_CURATED_QUERY_1",
            "REPLACE_WITH_GPT_5_4_MINI_CURATED_QUERY_2",
            "REPLACE_WITH_GPT_5_4_MINI_CURATED_QUERY_3"
        ) | ConvertTo-Json -Depth 5 | Set-Content -Path $QUERIES_FILE -Encoding utf8
    }
    Add-Content -Path $STATUS -Value "`n## NEEDS_CORPUS`n- QMD hits above threshold: $($hits.Count)`n- Recoverable sources: $($uniqueAssets.Count)`n- Queries file: $QUERIES_FILE"
    Write-Host "`nNEEDS_CORPUS" -ForegroundColor Yellow
    Write-Host "Recoverable sources: $($uniqueAssets.Count); required: $MinSources"
    Write-Host "Queries file: $QUERIES_FILE"
    Write-Host "Subagent prompt: $CORPUS_PLANNER_PROMPT"
    Write-Host "`nSuggested corpus queries:" -ForegroundColor Cyan
    Get-Content -LiteralPath $QUERIES_FILE -Raw -Encoding utf8 | Write-Host
    Write-Host "Use gpt-5.4-mini with the subagent prompt to replace these placeholders before launching corpus."
    Write-Host "Queries quality controls source quality."
    Write-Host "Confirm corpus creation, then run:"
    Write-Host "powershell.exe -ExecutionPolicy Bypass -File `"$AUTORESEARCH\scripts\run_hermes_pipeline.ps1`" -Slug `"$Slug-corpus`" -Goal `"$Question`" -QueriesFile `"$QUERIES_FILE`" -NotebookTitle `"Corpus - $NOTEBOOK_TITLE`" -Dashboard `"$Dashboard`""
    exit 2
}

if ($Mode -eq "thesis" -and -not $FromExistingQuestions) {
    $sourceTitles = @($uniqueAssets | ForEach-Object { $_.Title })
    Set-Content -Path $QUESTION_PLANNER_PROMPT -Encoding utf8 -Value @"
# Thesis NotebookLM Question Planner Subagent Task

Use model: gpt-5.4-mini.

Return JSON only. Do not run tools. Do not answer the questions.

Input JSON:

{
  "slug": "$Slug",
  "goal": "$Question",
  "dashboard": "$Dashboard",
  "mode": "thesis",
  "source_titles": $(ConvertTo-Json $sourceTitles -Compress)
}

Required output JSON:

{
  "slug": "$Slug",
  "goal": "$Question",
  "dashboard": "$Dashboard",
  "questions": [
    {
      "id": 1,
      "theme": "core-claim",
      "question": "focused NotebookLM question",
      "status": "pending"
    }
  ]
}

Rules:

- IDs are integers.
- Create 4-7 focused questions for thesis writing.
- Cover central claim, evidence, mechanisms/comparisons, limits, unsupported claims.
- Do not collapse the writing task into one broad QA.
- Questions must force cited NotebookLM answers from multiple sources where possible.
"@
    $template = [ordered]@{
        slug = $Slug
        goal = $Question
        dashboard = $Dashboard
        questions = @(
            [ordered]@{ id = 1; theme = "core-claim"; question = ""; status = "pending" },
            [ordered]@{ id = 2; theme = "evidence"; question = ""; status = "pending" },
            [ordered]@{ id = 3; theme = "limits"; question = ""; status = "pending" }
        )
    }
    $template | ConvertTo-Json -Depth 20 | Set-Content -Path $QUESTIONS_FILE -Encoding utf8
    Add-Content -Path $STATUS -Value "`n## NEEDS_QUESTIONS`n- Mode: thesis`n- Questions file: $QUESTIONS_FILE`n- Subagent prompt: $QUESTION_PLANNER_PROMPT"
    Write-Host "`nNEEDS_QUESTIONS" -ForegroundColor Yellow
    Write-Host "Mode thesis requires gpt-5.4-mini curated NotebookLM questions."
    Write-Host "Questions file: $QUESTIONS_FILE"
    Write-Host "Subagent prompt: $QUESTION_PLANNER_PROMPT"
    Write-Host "Resume after filling questions:"
    Write-Host "powershell.exe -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Question `"$Question`" -Mode thesis -Slug `"$Slug`" -Dashboard `"$Dashboard`" -FromExistingQuestions"
    exit 2
}

Write-Host "`n=== Create NotebookLM question notebook ===" -ForegroundColor Cyan
$listOutput = & notebooklm list 2>&1
if ($LASTEXITCODE -ne 0) { Fail "notebooklm list failed; run scripts\auto_login.ps1" }
$createOutput = & notebooklm create $NOTEBOOK_TITLE 2>&1
if ($LASTEXITCODE -ne 0) { Fail "notebooklm create failed: $($createOutput | Out-String)" }
$NOTEBOOK_ID = Get-NotebookIdFromText $createOutput
if (-not $NOTEBOOK_ID) { Fail "Could not parse NotebookLM notebook ID" }
Add-Content -Path $STATUS -Value "`n## Notebook`n- Title: $NOTEBOOK_TITLE`n- ID: $NOTEBOOK_ID"
Write-Host "Notebook ID: $NOTEBOOK_ID"

Write-Host "`n=== Add sources ===" -ForegroundColor Cyan
$pdfsToUpload = @()
foreach ($asset in $uniqueAssets) {
    if ($asset.Pdf) {
        $dest = Join-Path $PDF_DIR ([IO.Path]::GetFileName($asset.Pdf))
        Copy-Item -LiteralPath $asset.Pdf -Destination $dest -Force
        $pdfsToUpload += (Get-Item -LiteralPath $dest)
    } elseif ($asset.Url) {
        & notebooklm source add --notebook $NOTEBOOK_ID $asset.Url
        if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] URL upload failed: $($asset.Url)" -ForegroundColor Yellow }
    }
}
if ($pdfsToUpload.Count -gt 0) {
    $pdfsToUpload | ForEach-Object { $_.Name } | Set-Content -Path $PDF_LIST -Encoding utf8
    & $UPLOADER -NotebookId $NOTEBOOK_ID -PdfsDir $PDF_DIR -PdfList $PDF_LIST -Workers $Workers -LogFile $UPLOAD_LOG
    if ($LASTEXITCODE -ne 0) { Fail "parallel PDF upload failed; see $UPLOAD_LOG" }
}
Add-Content -Path $STATUS -Value "- Recoverable sources uploaded: $($uniqueAssets.Count)"

Write-Host "`n=== Export sources ===" -ForegroundColor Cyan
$UVPY = $VENV_PY
& $UVPY (Join-Path $SCRIPTS "list_sources_to_json.py") --notebook $NOTEBOOK_ID --out $TMP_SOURCES --title $NOTEBOOK_TITLE
if ($LASTEXITCODE -ne 0) { Fail "list_sources_to_json.py failed" }
$removedErrored = Remove-NotebookSourcesByStatus -NotebookId $NOTEBOOK_ID
if ($removedErrored -gt 0) {
    & $UVPY (Join-Path $SCRIPTS "list_sources_to_json.py") --notebook $NOTEBOOK_ID --out $TMP_SOURCES --title $NOTEBOOK_TITLE
    if ($LASTEXITCODE -ne 0) { Fail "list_sources_to_json.py failed after dropping errored sources" }
}
Assert-NotebookSourcesReady $NOTEBOOK_ID

Write-Host "`n=== Import sources and ask NotebookLM ===" -ForegroundColor Cyan
Push-Location $VAULT
try {
    & $VENV_PY (Join-Path $SCRIPTS "import_sources.py") `
        --sources $TMP_SOURCES `
        --slug $Slug `
        --dashboard $Dashboard `
        --papers-dir $PDF_DIR `
        --skip-guides
    if ($LASTEXITCODE -ne 0) { Fail "import_sources.py failed" }

    if ($FromExistingQuestions) {
        if (-not (Test-Path $QUESTIONS_FILE)) {
            Fail "FromExistingQuestions set but questions file not found: $QUESTIONS_FILE"
        }
        $questionsPayload = Get-Content -LiteralPath $QUESTIONS_FILE -Raw -Encoding utf8 | ConvertFrom-Json
        if ($questionsPayload.PSObject.Properties.Name -contains "notebook_id") {
            $questionsPayload.notebook_id = $NOTEBOOK_ID
        } else {
            $questionsPayload | Add-Member -NotePropertyName "notebook_id" -NotePropertyValue $NOTEBOOK_ID
        }
        if ($questionsPayload.PSObject.Properties.Name -contains "dashboard") {
            $questionsPayload.dashboard = $Dashboard
        } else {
            $questionsPayload | Add-Member -NotePropertyName "dashboard" -NotePropertyValue $Dashboard
        }
        $filledExisting = @($questionsPayload.questions | Where-Object { $_.question -and $_.question.Trim().Length -gt 0 })
        if ($filledExisting.Count -eq 0) {
            Fail "Questions file has no filled questions: $QUESTIONS_FILE" 2
        }
        $questionsPayload | ConvertTo-Json -Depth 20 | Set-Content -Path $QUESTIONS_FILE -Encoding utf8
    } else {
        $questionItems = @(
            [ordered]@{
                id = 1
                theme = $Mode
                question = $Question
                status = "pending"
            }
        )

        $questionsPayload = [ordered]@{
            slug = $Slug
            goal = $Question
            dashboard = $Dashboard
            notebook_id = $NOTEBOOK_ID
            questions = $questionItems
        }
        $questionsPayload | ConvertTo-Json -Depth 20 | Set-Content -Path $QUESTIONS_FILE -Encoding utf8
    }

    $blockTitle = if ($Mode -eq "thesis") { "$Dashboard - thesis evidence" } else { "$Dashboard - answer evidence" }
    & $VENV_PY (Join-Path $SCRIPTS "batch_ask.py") `
        --questions $QUESTIONS_FILE `
        --sources $TMP_SOURCES `
        --notebook-id $NOTEBOOK_ID `
        --tmp-dir $RUN_DIR `
        --block-summary-title $blockTitle
    if ($LASTEXITCODE -ne 0) { Fail "batch_ask.py failed" }

    & qmd update
    if ($LASTEXITCODE -ne 0) { Fail "qmd update failed" }
} finally {
    Pop-Location
}

$updatedQuestions = Get-Content -LiteralPath $QUESTIONS_FILE -Raw -Encoding utf8 | ConvertFrom-Json
Add-Content -Path $STATUS -Value "`n## Outputs"
foreach ($field in @("qa_summary_note", "source_curation_note", "block_summary_note")) {
    if ($updatedQuestions.$field) {
        Add-Content -Path $STATUS -Value "- ${field}: $($updatedQuestions.$field)"
        Write-Host "${field}: $($updatedQuestions.$field)"
    }
}
Write-Host "`nDone. NotebookLM evidence exported under Notes/NotebookLM/$Slug" -ForegroundColor Green
