$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& '.\.venv\Scripts\python.exe' scripts/run_demo.py
if ($LASTEXITCODE -ne 0) { throw 'Demo startup failed. Inspect .runtime logs.' }
