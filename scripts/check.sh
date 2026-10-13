#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python -m pytest backend/tests scripts/tests -q
.venv/bin/python scripts/validate_sources.py
npm --prefix contracts test
npm --prefix contracts run test:bridge
npm --prefix frontend run typecheck
npm --prefix frontend run build
printf '%s\n' 'Checks passed. With the local demo running: npm --prefix frontend run test:e2e'
