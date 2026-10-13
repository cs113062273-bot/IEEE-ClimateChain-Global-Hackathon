$ErrorActionPreference = 'Stop'
$taskContracts = Split-Path -Parent $PSScriptRoot
Push-Location $taskContracts
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Contract build failed' }
    & node.exe (Join-Path $PSScriptRoot 'start-local.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Local chain startup failed' }
} finally { Pop-Location }
