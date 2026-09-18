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
    [int]$Workers = 4,
    [string]$LogFile = "C:\tmp\upload_parallel.log"
)

$uploader = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "scripts\upload_sources_parallel.ps1"
& $uploader @PSBoundParameters
exit $LASTEXITCODE
