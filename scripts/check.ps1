$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m pytest backend/tests scripts/tests -q
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
& '.\.venv\Scripts\python.exe' scripts/validate_sources.py
if ($LASTEXITCODE -ne 0) { throw 'Source audit failed.' }
& npm.cmd --prefix contracts test
if ($LASTEXITCODE -ne 0) { throw 'Contract tests failed.' }
& npm.cmd --prefix contracts run test:bridge
if ($LASTEXITCODE -ne 0) { throw 'Bridge tests failed.' }
& npm.cmd --prefix frontend run typecheck
if ($LASTEXITCODE -ne 0) { throw 'Frontend typecheck failed.' }
& npm.cmd --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Host 'Checks passed. With the local demo running: npm --prefix frontend run test:e2e'
