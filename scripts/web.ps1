$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$webRoot = Join-Path $projectRoot "web"
$bundledNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$systemNode = Get-Command node -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $bundledNode) {
    $node = $bundledNode
} elseif ($systemNode) {
    $node = $systemNode.Source
} else {
    throw "Node.js 22+ was not found."
}

$vinext = Join-Path $webRoot "node_modules\vinext\dist\cli.js"
if (-not (Test-Path -LiteralPath $vinext)) {
    throw "Web dependencies are not installed. See web\README.md."
}

Push-Location $webRoot
try {
    $env:WRANGLER_LOG_PATH = ".wrangler/wrangler.log"
    & $node $vinext build
    if ($LASTEXITCODE -ne 0) { throw "Web build failed." }
    & $node $vinext start --host 0.0.0.0
} finally {
    Pop-Location
}
