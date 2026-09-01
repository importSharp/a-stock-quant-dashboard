param(
    [Parameter(Position = 0)]
    [string]$Command = "scan",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$bundledPython = "C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$systemPython = Get-Command python -ErrorAction SilentlyContinue
if ($systemPython) {
    $python = $systemPython.Source
} elseif (Test-Path -LiteralPath $bundledPython) {
    $python = $bundledPython
} else {
    throw "未找到 Python 3.11+；请安装 Python 或修改 scripts/run.ps1 中的路径。"
}
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"
& $python -m aquant_limitup.cli $Command @Rest
exit $LASTEXITCODE
