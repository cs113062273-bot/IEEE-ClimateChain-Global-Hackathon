#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
npm --prefix frontend ci --no-audit --no-fund
npm --prefix contracts ci --no-audit --no-fund
npm --prefix contracts run build
# Real workplace sessions (4TU.ResearchData, CC BY-NC-SA 4.0, no account). Not redistributed in this repository.
.venv/bin/python scripts/fetch_workplace_sessions.py
if [ "${1:-}" = "--download-data" ]; then
  .venv/bin/python scripts/discover_sources.py
  .venv/bin/python scripts/fetch_neso.py
  .venv/bin/python scripts/fetch_openmeteo.py
  .venv/bin/python scripts/fetch_pvgis.py
  .venv/bin/python scripts/build_snapshot.py
  .venv/bin/python scripts/profile_sources.py
  .venv/bin/python scripts/validate_sources.py --require-bulk --write-manifest
fi
printf '%s\n' 'Setup complete. Run: sh scripts/run_demo.sh'
