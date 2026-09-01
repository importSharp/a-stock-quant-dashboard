param(
    [int]$IntervalSeconds = 30,
    [switch]$Once
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$systemPython = Get-Command python -ErrorAction SilentlyContinue
$pythonCandidates = @(
    (Join-Path $projectRoot ".venv\Scripts\python.exe"),
    (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    $(if ($systemPython) { $systemPython.Source })
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$pythonPath = $pythonCandidates | Select-Object -First 1
if (-not $pythonPath) {
    throw "Python 3.11+ was not found."
}

do {
    & $pythonPath "$PSScriptRoot\a_stock_data_snapshot.py"
    if ($LASTEXITCODE -ne 0) { throw "a-stock-data snapshot refresh failed." }
    if ($Once) { break }
    Start-Sleep -Seconds ([Math]::Max($IntervalSeconds, 60))
} while ($true)
