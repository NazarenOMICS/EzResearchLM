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

$pdfs   = @(Get-Content -LiteralPath $PdfList -Encoding utf8 | Where-Object { $_.Trim() -ne "" })
$total  = $pdfs.Count
$script:ok   = 0
$script:fail = 0
$mutex  = [System.Threading.Mutex]::new($false)

Set-Content -Path $LogFile -Value "[$(Get-Date -Format 'HH:mm:ss')] Starting parallel upload: $total PDFs, $Workers workers"
Write-Host "Uploading $total PDFs with $Workers parallel workers..."

# Split into batches for each worker
$batches = @()
for ($i = 0; $i -lt $Workers; $i++) { $batches += ,@() }
for ($i = 0; $i -lt $pdfs.Count; $i++) { $batches[$i % $Workers] += $pdfs[$i] }

$jobs = @()
foreach ($batch in $batches) {
    if ($batch.Count -eq 0) { continue }
    $jobs += Start-Job -ScriptBlock {
        param($nb, $dir, $filesText, $log)
        $results = @()
        $files = @($filesText -split "\|" | Where-Object { $_ })
        foreach ($fname in $files) {
            $path   = Join-Path $dir $fname
            $result = & notebooklm source add --notebook $nb --type file --mime-type application/pdf $path 2>&1
            $status = if ($LASTEXITCODE -eq 0) { "OK" } else { "FAIL" }
            $msg    = "[$(Get-Date -Format 'HH:mm:ss')] $status - $fname"
            if ($status -eq "FAIL") {
                $msg = "$msg :: $(($result | Out-String).Trim())"
            }
            Add-Content -Path $log -Value $msg
            $results += "$status|$fname"
        }
        return $results
    } -ArgumentList $NotebookId, $PdfsDir, ($batch -join "|"), $LogFile
}

# Wait for all jobs
$allResults = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job

# Tally
foreach ($line in $allResults) {
    if ($line -match "^OK\|")   { $script:ok++ }
    if ($line -match "^FAIL\|") { $script:fail++ }
}

$summary = "DONE: $($script:ok) OK, $($script:fail) FAIL (of $total)"
Add-Content -Path $LogFile -Value "[$(Get-Date -Format 'HH:mm:ss')] $summary"
Write-Host $summary
