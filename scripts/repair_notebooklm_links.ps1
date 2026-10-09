param(
    [Parameter(Mandatory = $true)]
    [string]$Root,

    [Parameter(Mandatory = $true)]
    [string]$OldVaultSlug,

    [Parameter(Mandatory = $true)]
    [string]$NewVaultSlug,

    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
$oldSlug = ($OldVaultSlug -replace "\\", "/").Trim("/")
$newSlug = ($NewVaultSlug -replace "\\", "/").Trim("/")
$oldNeedle = "Notes/NotebookLM/$oldSlug"
$newNeedle = "Notes/NotebookLM/$newSlug"

$files = @(Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File -Filter "*.md")
$changed = 0
$mentions = 0

foreach ($file in $files) {
    $text = Get-Content -LiteralPath $file.FullName -Raw -Encoding utf8
    $count = ([regex]::Matches($text, [regex]::Escape($oldNeedle))).Count
    if ($count -eq 0) { continue }

    $mentions += $count
    $changed += 1
    $updated = $text.Replace($oldNeedle, $newNeedle)

    if ($WhatIf) {
        Write-Host "WOULD_UPDATE $($file.FullName) ($count mention(s))"
    } else {
        Set-Content -LiteralPath $file.FullName -Value $updated -Encoding utf8 -NoNewline
        Write-Host "UPDATED $($file.FullName) ($count mention(s))"
    }
}

Write-Host "Done: $changed file(s), $mentions mention(s)"

