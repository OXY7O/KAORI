#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() {
    printf '[KAORI frontend bootstrap] %s\n' "$*"
}

fail() {
    printf '[KAORI frontend bootstrap] ERROR: %s\n' "$*" >&2
    exit 1
}

command -v node >/dev/null 2>&1 || fail 'Node.js is unavailable.'
command -v npm >/dev/null 2>&1 || fail 'npm is unavailable.'
[[ -f package.json ]] || fail 'package.json was not found.'
[[ -f package-lock.json ]] || fail 'package-lock.json was not found.'

log 'Installing exact frontend dependencies from package-lock.json...'
npm ci --no-audit --no-fund

log 'Preparing pinned browser-ready vendor assets and locally generated CSS...'
npm run prepare-frontend

log 'Running frontend functional and contract gates...'
./scripts/test_offline_frontend.sh

log 'Frontend bootstrap completed.'
log 'Commit app/static/vendor and intentional source changes only; app/static/css/output.css is generated and ignored.'
