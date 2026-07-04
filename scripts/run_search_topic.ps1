param(
    [Parameter(Mandatory = $true)]
    [string]$Slug,

    [Parameter(Mandatory = $true)]
    [string]$QueriesFile,

    [string]$SaveDir,

    [string]$Sources = 'pubmed,europepmc,openalex,semantic,crossref',
    [int]$TopN = 5,
    [switch]$MinOa,
    [switch]$StdoutJson,
    [string]$MustHaveFile,
    [switch]$AllowAnnaFallback,
    [switch]$ScoutOnly,
    [switch]$ResolveOnly
)

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
$paperSearchPath = Join-Path $EZRESEARCH_ROOT "packages\paper_search"
$SEARCH_ROOT = if ($env:EZRESEARCH_SEARCH_ROOT) { $env:EZRESEARCH_SEARCH_ROOT } else { Join-Path $EZRESEARCH_ROOT "Search" }
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$paperSearchPath;$env:PYTHONPATH" } else { $paperSearchPath }
$pythonCandidates = @(
    $env:EZRESEARCH_PYTHON,
    (Join-Path $EZRESEARCH_ROOT ".venv\Scripts\python.exe"),
    (Join-Path $EZRESEARCH_ROOT ".pdfenv\.venv\Scripts\python.exe"),
    "python"
) | Where-Object { $_ }
$PYTHON = @($pythonCandidates | Where-Object { $_ -eq "python" -or (Test-Path -LiteralPath $_) } | Select-Object -First 1)[0]
if (-not $SaveDir) {
    $SaveDir = Join-Path $SEARCH_ROOT "$Slug-papers"
}

$args = @(
    (Join-Path $paperSearchPath "run_search_topic_wrapper.py"),
    '--slug', $Slug,
    '--queries-file', $QueriesFile,
    '--sources', $Sources,
    '--n', $TopN.ToString(),
    '--save-dir', $SaveDir
)

if ($MinOa) { $args += '--min-oa' }
if ($StdoutJson) { $args += '--stdout-json' }
if ($MustHaveFile) { $args += @('--must-have-file', $MustHaveFile) }
if ($AllowAnnaFallback) { $args += '--allow-anna-fallback' }
if ($ScoutOnly) { $args += '--scout-only' }
if ($ResolveOnly) { $args += '--resolve-only' }

& $PYTHON @args
exit $LASTEXITCODE
