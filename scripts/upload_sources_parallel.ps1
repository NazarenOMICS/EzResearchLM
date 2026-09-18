<#
.SYNOPSIS
    Upload PDFs to a NotebookLM notebook in parallel (N workers).
    Logs results to --log-file.

.USAGE
    upload_sources_parallel.ps1 -NotebookId <uuid> -PdfsDir <dir> -PdfList <file> [-Workers 4] [-LogFile <path>]

    PdfList: text file with one PDF filename per line (relative to PdfsDir)

.EXAMPLE
    $pdfs = @("paper1.pdf","paper2.pdf")
    $pdfs | Out-File C:\tmp\list.txt
    upload_sources_parallel.ps1 -NotebookId abc -PdfsDir C:\papers -PdfList C:\tmp\list.txt
#>
param(
    [Parameter(Mandatory)][string]$NotebookId,
    [Parameter(Mandatory)][string]$PdfsDir,
    [Parameter(Mandatory)][string]$PdfList,
    [ValidateRange(1, 8)][int]$Workers = 4,
    [string]$LogFile = "C:\tmp\upload_parallel.log"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @($env:EZRESEARCH_PYTHON, (Join-Path $repoRoot ".venv\Scripts\python.exe"), "python") | Where-Object { $_ }
$python = @($pythonCandidates | Where-Object { $_ -eq "python" -or (Test-Path -LiteralPath $_) } | Select-Object -First 1)[0]
$external = Join-Path $PSScriptRoot "run_external.py"
& $python $external --timeout 1815 -- $python -m ez.upload --notebook $NotebookId --directory $PdfsDir --list $PdfList --workers $Workers --log $LogFile
exit $LASTEXITCODE
