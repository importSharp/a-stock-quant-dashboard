param(
    [int]$IntervalSeconds = 60,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot "data\runtime"
$scannerPidPath = Join-Path $runtimeRoot "mobile-scanner.pid"
$webPidPath = Join-Path $runtimeRoot "mobile-web.pid"
$scannerOutPath = Join-Path $runtimeRoot "mobile-scanner.log"
$scannerErrorPath = Join-Path $runtimeRoot "mobile-scanner-error.log"
$webOutPath = Join-Path $runtimeRoot "mobile-web.log"
$webErrorPath = Join-Path $runtimeRoot "mobile-web-error.log"

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

function Get-SavedProcess {
    param([string]$PidPath)
    if (-not (Test-Path -LiteralPath $PidPath)) { return $null }
    try {
        $record = Get-Content -LiteralPath $PidPath -Raw | ConvertFrom-Json
        $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
        if (-not $process) { return $null }
        $actualStart = $process.StartTime.ToUniversalTime().ToString("o")
        if ($actualStart -ne [string]$record.startTime) { return $null }
        return $process
    } catch {
        return $null
    }
}

function Save-ProcessInfo {
    param($Process, [string]$PidPath)
    @{
        pid = $Process.Id
        startTime = $Process.StartTime.ToUniversalTime().ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $PidPath
}

function Test-WebReady {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:3000/" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Get-SavedProcess -PidPath $scannerPidPath)) {
    $scannerArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $PSScriptRoot "mobile-refresh.ps1"),
        "-IntervalSeconds", ([Math]::Max($IntervalSeconds, 60))
    )
    $scanner = Start-Process powershell.exe `
        -ArgumentList $scannerArgs `
        -WindowStyle Hidden `
        -RedirectStandardOutput $scannerOutPath `
        -RedirectStandardError $scannerErrorPath `
        -PassThru
    Save-ProcessInfo -Process $scanner -PidPath $scannerPidPath
    Write-Host "[STARTED] a-stock-data refresher PID $($scanner.Id)"
} else {
    Write-Host "[RUNNING] a-stock-data refresher"
}

if (-not (Test-WebReady) -and -not (Get-SavedProcess -PidPath $webPidPath)) {
    $webArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $PSScriptRoot "web.ps1")
    )
    $web = Start-Process powershell.exe `
        -ArgumentList $webArgs `
        -WindowStyle Hidden `
        -RedirectStandardOutput $webOutPath `
        -RedirectStandardError $webErrorPath `
        -PassThru
    Save-ProcessInfo -Process $web -PidPath $webPidPath
    Write-Host "[STARTED] web server PID $($web.Id)"
} else {
    Write-Host "[RUNNING] web server"
}

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if (Test-WebReady) {
        $ready = $true
        break
    }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    throw "Web server was not ready in 15 seconds. See $webErrorPath"
}

Write-Host "[READY] http://localhost:3000/"
Write-Host "Mobile LAN URL: http://YOUR-LAN-IP:3000/"
if (-not $NoOpen) {
    Start-Process "http://localhost:3000/"
}
