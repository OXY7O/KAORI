#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .git ]]; then
    printf '[KAORI hygiene] Git metadata is unavailable; tracked-file validation was skipped.\n'
    exit 0
fi

mapfile -t tracked < <(git ls-files)
violations=()
for path in "${tracked[@]}"; do
    case "$path" in
        *__pycache__/*|*.pyc|*.pyo|.pytest_cache/*|.ruff_cache/*|.mypy_cache/*|node_modules/*|instance/*|reports/generated/*|tmp/*|*.zip)
            violations+=("$path")
            ;;
    esac
done

if (( ${#violations[@]} > 0 )); then
    printf 'ERROR: generated/runtime artifacts are tracked:\n' >&2
    printf '  %s\n' "${violations[@]}" >&2
    exit 1
fi

for required in .gitignore .dockerignore; do
    [[ -f "$required" ]] || {
        printf 'ERROR: %s is required.\n' "$required" >&2
        exit 1
    }
done

printf '[KAORI hygiene] Tracked source is clean (%s files checked).\n' "${#tracked[@]}"
