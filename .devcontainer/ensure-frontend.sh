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

repair_frontend_output_permissions() {
    local paths=(
        'app/static/css'
        'app/static/fonts'
        'app/static/vendor'
    )
    local existing_paths=()
    local path
    local needs_repair=false

    for path in "${paths[@]}"; do
        [[ -e "$path" ]] || continue
        existing_paths+=("$path")
        if [[ ! -w "$path" ]] || find "$path" ! -writable -print -quit | grep -q .; then
            needs_repair=true
        fi
    done

    [[ "$needs_repair" == true ]] || return 0
    command -v sudo >/dev/null 2>&1 || fail 'Generated frontend outputs are not writable and sudo is unavailable to repair their ownership.'

    log 'Repairing generated frontend output ownership for the current Dev Container user...'
    sudo chown -R "$(id -u):$(id -g)" "${existing_paths[@]}"
}

command -v node >/dev/null 2>&1 || fail 'Node.js is unavailable. Rebuild the devcontainer so the Node feature can be installed.'
command -v npm >/dev/null 2>&1 || fail 'npm is unavailable. Rebuild the devcontainer so the Node feature can be installed.'

[[ -f package.json ]] || fail 'package.json was not found in /workspace/kaori.'
[[ -f package-lock.json ]] || fail 'package-lock.json was not found in /workspace/kaori.'

if grep -q 'internal\.api\.openai\.org' package-lock.json; then
    fail 'package-lock.json still references an internal package registry. Apply the canonical KAORI lockfile before rebuilding.'
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
elif [[ ! -f node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2 ]]; then
    install_required=true
elif [[ "$stored_hash" != "$lock_hash" ]]; then
    install_required=true
fi

if [[ "$install_required" == true ]]; then
    log 'Installing frontend dependencies with npm ci...'
    # Fail predictably on registry problems instead of waiting through npm's
    # long default network timeouts. Reuse the cache whenever possible.
    if ! npm ci --no-audit --no-fund --prefer-offline --fetch-retries=1 --fetch-timeout=30000; then
        fail 'npm ci failed. Inspect the npm registry/network error above; node_modules is not ready.'
    fi
    [[ -x node_modules/.bin/tailwindcss ]] || fail 'Tailwind CLI was not installed in node_modules/.bin.'
    printf '%s\n' "$lock_hash" > "$stamp_file"
else
    log 'Frontend dependencies match package-lock.json.'
fi

repair_frontend_output_permissions

# This stamp lives in the node_modules volume and is invalidated when
# frontend source, template classes, or vendoring/build scripts change.
# The VS Code watcher handles subsequent CSS edits during an open session.
build_stamp='node_modules/.kaori-frontend-inputs.sha256'
inputs_hash="$(
    {
        sha256sum package.json package-lock.json \
            scripts/vendor_frontend_assets.mjs \
            scripts/verify_frontend_assets.mjs \
            scripts/verify_css_build.mjs
        find frontend app/templates app/static/js -type f -print0 \
            | LC_ALL=C sort -z \
            | xargs -0 -r sha256sum
    } | sha256sum | awk '{print $1}'
)"
stored_inputs_hash=''
if [[ -f "$build_stamp" ]]; then
    stored_inputs_hash="$(tr -d '[:space:]' < "$build_stamp")"
fi

if [[ "$install_required" == true ]] \
    || [[ "$stored_inputs_hash" != "$inputs_hash" ]] \
    || [[ ! -f app/static/css/output.css ]] \
    || [[ ! -f app/static/vendor/manifest.json ]] \
    || [[ ! -f app/static/fonts/inter/inter-latin-wght-normal.woff2 ]]; then
    log 'Vendoring browser dependencies and building Tailwind CSS...'
    npm run prepare-frontend
    printf '%s\n' "$inputs_hash" > "$build_stamp"
    log 'Frontend assets are local, verified, and ready.'
else
    log 'Frontend inputs unchanged; skipping redundant asset rebuild.'
fi
