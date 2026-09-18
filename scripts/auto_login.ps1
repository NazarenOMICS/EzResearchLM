param(
    [string]$StoragePath = $(if ($env:NOTEBOOKLM_STORAGE_STATE) { $env:NOTEBOOKLM_STORAGE_STATE } else { "$env:USERPROFILE\.notebooklm\profiles\default\storage_state.json" }),
    [int]$TimeoutSeconds = 600,
    [int]$PollSeconds = 3,
    [switch]$SkipBrowserLogin,
    [switch]$Manual,
    [ValidateSet('chromium', 'chrome', 'msedge')]
    [string]$Browser = 'chromium'
)

$ErrorActionPreference = 'Stop'
$loginRoot = Split-Path -Parent $PSScriptRoot
$loginExternal = Join-Path $PSScriptRoot 'run_external.py'
$loginPython = Join-Path $loginRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $loginPython)) { $loginPython = 'python' }

function Test-NotebookLMList {
    param([string]$Storage)

    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $result = & $loginPython $loginExternal --timeout 30 -- notebooklm --storage $Storage list 2>&1
        $exitCode = $LASTEXITCODE
    } catch {
        $result = @($_.Exception.Message)
        $exitCode = 1
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
    return @{
        ExitCode = $exitCode
        Output = ($result | Out-String)
    }
}

function Test-NotebookLMAuthenticated {
    param([string]$Storage)
    $check = Test-NotebookLMList -Storage $Storage
    return ($check.ExitCode -eq 0)
}

$attemptId = Get-Date -Format 'yyyyMMdd-HHmmss'
Write-Host "AUTO_LOGIN_ATTEMPT: $attemptId"
Write-Host "Using storage: $StoragePath"

$storageDir = Split-Path -Parent $StoragePath
if (-not (Test-Path $storageDir)) {
    New-Item -ItemType Directory -Path $storageDir -Force | Out-Null
}

$precheck = Test-NotebookLMList -Storage $StoragePath
if ($precheck.ExitCode -eq 0) {
    Write-Host "ALREADY_AUTHENTICATED"
    Write-Host "LOGIN SUCCESS"
    exit 0
}

$originalTime = if (Test-Path $StoragePath) { (Get-Item $StoragePath).LastWriteTime } else { [datetime]::MinValue }

if (-not $SkipBrowserLogin) {
    $loginArgs = @('--storage', $StoragePath, 'login', '--browser', $Browser)
    $proc = Start-Process -FilePath "notebooklm.exe" `
        -ArgumentList $loginArgs `
        -PassThru -WindowStyle Normal
    Write-Host "Login window opened. Waiting for browser auth..."
    Write-Host "Manual mode: $([bool]$Manual)"
} else {
    $proc = $null
    Write-Host "SkipBrowserLogin enabled. Waiting only for storage update..."
}

$loginClock = [System.Diagnostics.Stopwatch]::StartNew()
$authDetected = $false
while ($loginClock.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    Start-Sleep -Seconds $PollSeconds

    if (Test-Path $StoragePath) {
        $currentTime = (Get-Item $StoragePath).LastWriteTime
        if ($currentTime -gt $originalTime) {
            Write-Host "Auth detected (storage_state.json updated at $currentTime)"
            $authDetected = $true
            break
        }
    }

    if (Test-NotebookLMAuthenticated -Storage $StoragePath) {
        Write-Host "Auth verified via notebooklm list before file mtime changed"
        $authDetected = $true
        break
    }
}

if (-not $authDetected) {
    Write-Host "ERROR: Auth not detected within $TimeoutSeconds seconds"
    exit 1
}

Start-Sleep -Seconds 3

if ($proc -and -not $Manual) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $wshell = New-Object -ComObject WScript.Shell
        $activated = $wshell.AppActivate($proc.Id)
        if (-not $activated) {
            $activated = $wshell.AppActivate('notebooklm')
        }
        Start-Sleep -Milliseconds 500
        if ($activated) {
            $wshell.SendKeys('{ENTER}')
            Write-Host 'Enter sent to login window'
        } else {
            Write-Host 'WARN: Could not activate login window. Manual Enter may be needed.'
        }
    } catch {
        Write-Host "WARN: Auto-Enter failed: $($_.Exception.Message)"
    }

    try {
        $proc | Wait-Process -Timeout 30 -ErrorAction SilentlyContinue
    } catch {
    }
}

$authResult = Test-NotebookLMList -Storage $StoragePath
if ($authResult.ExitCode -eq 0) {
    Write-Host 'LOGIN SUCCESS'
    exit 0
}

Write-Host "LOGIN FAILED: $($authResult.Output)"
exit 1
