# One-time setup on Windows (PowerShell). Needs Python 3.11+ and Node 24.
# Native tools write notices to stderr, so failures are detected by exit code, not by stderr.
$ep = Split-Path -Parent $PSScriptRoot
Set-Location $ep

function Step($what, [scriptblock]$cmd) {
    Write-Host "== $what"
    & $cmd
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $what (exit $LASTEXITCODE)"; exit 1 }
}

if (-not (Test-Path .venv)) { Step "create Python environment" { python -m venv .venv } }
Step "install Python packages" { .\.venv\Scripts\python -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt }
Set-Location contracts
Step "install contract tooling" { npm ci --no-audit --no-fund }
Step "compile contracts" { npx hardhat build }
Set-Location ..\web
Step "install web app" { npm ci --no-audit --no-fund }
Step "build web app" { npm run build }
Set-Location ..
Write-Host "Ready. Start the demo from the repository root with:"
Write-Host "  extremeproof\.venv\Scripts\python -m extremeproof.scripts.stack"
