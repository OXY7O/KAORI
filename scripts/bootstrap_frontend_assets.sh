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

log 'Synchronizing exact frontend runtime dependencies and package-lock.json...'
npm install --save-dev --save-exact --no-audit --no-fund \
    alpinejs@3.15.12 \
    htmx.org@2.0.10 \
    lucide@1.20.0 \
    chart.js@4.5.1

log 'Creating committed browser-ready vendor assets and compiled CSS...'
npm run prepare-frontend

log 'Running frontend functional and contract gates...'
./scripts/test_offline_frontend.sh

log 'Frontend bootstrap completed.'
log 'Commit package-lock.json, app/static/vendor, app/static/css/output.css, and the source changes.'
