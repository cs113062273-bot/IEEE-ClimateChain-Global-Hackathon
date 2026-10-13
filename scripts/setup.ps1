param([switch]$DownloadData)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed to install.' }
& npm.cmd --prefix frontend ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed to install.' }
& npm.cmd --prefix contracts ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Contract dependencies failed to install.' }
& npm.cmd --prefix contracts run build
if ($LASTEXITCODE -ne 0) { throw 'Contract compilation failed.' }
if ($DownloadData) {
    & '.\.venv\Scripts\python.exe' scripts/discover_sources.py
    if ($LASTEXITCODE -ne 0) { throw 'Source discovery failed.' }
    & '.\.venv\Scripts\python.exe' scripts/fetch_neso.py
    if ($LASTEXITCODE -ne 0) { throw 'NESO download failed.' }
    & '.\.venv\Scripts\python.exe' scripts/fetch_openmeteo.py
    if ($LASTEXITCODE -ne 0) { throw 'Open-Meteo download failed.' }
    & '.\.venv\Scripts\python.exe' scripts/fetch_pvgis.py
    if ($LASTEXITCODE -ne 0) { throw 'PVGIS download failed.' }
    & '.\.venv\Scripts\python.exe' scripts/build_snapshot.py
    if ($LASTEXITCODE -ne 0) { throw 'Snapshot preparation failed.' }
    & '.\.venv\Scripts\python.exe' scripts/profile_sources.py
    if ($LASTEXITCODE -ne 0) { throw 'Data profiling failed.' }
    & '.\.venv\Scripts\python.exe' scripts/validate_sources.py --require-bulk --write-manifest
    if ($LASTEXITCODE -ne 0) { throw 'Data validation failed; inspect source audit.' }
}
Write-Host 'Setup complete. Run: .\scripts\run_demo.ps1'
