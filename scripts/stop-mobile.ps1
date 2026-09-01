$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot "data\runtime"
$pidFiles = @(
    (Join-Path $runtimeRoot "mobile-scanner.pid"),
    (Join-Path $runtimeRoot "mobile-web.pid")
)

function Stop-ProcessTree {
    param([int]$RootProcessId)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -RootProcessId ([int]$child.ProcessId)
    }
    Stop-Process -Id $RootProcessId -Force -ErrorAction SilentlyContinue
}

foreach ($pidPath in $pidFiles) {
    if (-not (Test-Path -LiteralPath $pidPath)) { continue }
    try {
        $record = Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json
        $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
        if ($process -and $process.StartTime.ToUniversalTime().ToString("o") -eq [string]$record.startTime) {
            Stop-ProcessTree -RootProcessId $process.Id
            Write-Host "[STOPPED] PID $($process.Id)"
        }
    } catch {
        Write-Host "[SKIPPED] Invalid process record $pidPath"
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

Write-Host "a-stock-data dashboard services stopped."
