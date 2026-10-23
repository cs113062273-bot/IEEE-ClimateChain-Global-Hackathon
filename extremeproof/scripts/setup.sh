#!/usr/bin/env sh
# One-time setup on macOS/Linux. Needs Python 3.11+ and Node 24.
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv

.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
(cd contracts && npm ci --no-audit --no-fund && npx hardhat build)
(cd web && npm ci --no-audit --no-fund && npm run build)
echo "Ready. Start the demo from the repository root with:"
echo "  extremeproof/.venv/bin/python -m extremeproof.scripts.stack"
