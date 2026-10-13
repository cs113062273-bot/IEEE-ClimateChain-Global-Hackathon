#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
npm run build
node scripts/start-local.mjs
