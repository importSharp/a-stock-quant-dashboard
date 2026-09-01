param(
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$logDirectory = Join-Path $projectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDirectory "daily-$stamp.log"

Push-Location $projectRoot
try {
    if (-not $SkipSync) {
        & (Join-Path $PSScriptRoot "run.ps1") sync 2>&1 | Tee-Object -FilePath $logPath
        if ($LASTEXITCODE -ne 0) {
            throw "行情同步失败，退出码 $LASTEXITCODE"
        }
    }
    & (Join-Path $PSScriptRoot "run.ps1") scan 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "候选扫描失败，退出码 $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

