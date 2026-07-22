#!/usr/bin/env bash
set -Eeuo pipefail

cd /workspace/kaori

log() {
    printf '[KAORI frontend] %s\n' "$*"
}

fail() {
    printf '[KAORI frontend] ERROR: %s\n' "$*" >&2
    exit 1
}

command -v node >/dev/null 2>&1 || fail 'Node.js is unavailable. Rebuild the devcontainer so the Node feature can be installed.'
command -v npm >/dev/null 2>&1 || fail 'npm is unavailable. Rebuild the devcontainer so the Node feature can be installed.'

[[ -f package.json ]] || fail 'package.json was not found in /workspace/kaori.'
[[ -f package-lock.json ]] || fail 'package-lock.json was not found in /workspace/kaori.'

if grep -q 'internal\.api\.openai\.org' package-lock.json; then
    fail 'package-lock.json still references an internal package registry.'
fi

if ! node <<'NODE'
const lock = require('./package-lock.json')
const expected = {
  'node_modules/alpinejs': '3.15.12',
  'node_modules/htmx.org': '2.0.10',
  'node_modules/lucide': '1.20.0',
  'node_modules/chart.js': '4.5.1',
}
for (const [name, version] of Object.entries(expected)) {
  if (lock.packages?.[name]?.version !== version) process.exit(1)
}
NODE
then
    fail 'package-lock.json is not synchronized with pinned runtime assets. Run: npm run bootstrap-frontend'
fi

lock_hash="$(sha256sum package-lock.json | awk '{print $1}')"
stamp_file='node_modules/.kaori-package-lock.sha256'
stored_hash=''

if [[ -f "$stamp_file" ]]; then
    stored_hash="$(tr -d '[:space:]' < "$stamp_file")"
fi

install_required=false
if [[ "${1:-}" == '--install-always' ]]; then
    install_required=true
elif [[ ! -x node_modules/.bin/tailwindcss ]]; then
    install_required=true
elif [[ ! -f node_modules/lucide/dist/umd/lucide.min.js ]]; then
    install_required=true
elif [[ "$stored_hash" != "$lock_hash" ]]; then
    install_required=true
fi

if [[ "$install_required" == true ]]; then
    log 'Installing frontend dependencies with npm ci...'
    npm ci --no-audit --no-fund
    [[ -x node_modules/.bin/tailwindcss ]] || fail 'Tailwind CLI was not installed in node_modules/.bin.'
    printf '%s\n' "$lock_hash" > "$stamp_file"
else
    log 'Frontend dependencies match package-lock.json.'
fi

log 'Vendoring browser dependencies and building Tailwind CSS...'
npm run prepare-frontend
log 'Frontend assets are local, verified, and ready.'
