#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for required in .gitignore .dockerignore; do
    [[ -f "$required" ]] || {
        printf 'ERROR: %s is required.\n' "$required" >&2
        exit 1
    }
done

is_forbidden_path() {
    local path="$1"
    case "$path" in
        *__pycache__|*__pycache__/*|*.pyc|*.pyo|.pytest_cache|.pytest_cache/*|.ruff_cache|.ruff_cache/*|.mypy_cache|.mypy_cache/*|node_modules|node_modules/*|instance|instance/*|reports/generated|reports/generated/*|tmp|tmp/*|*.zip)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

violations=()
checked=0

if [[ -d .git ]]; then
    mapfile -t candidates < <(git -c safe.directory="$ROOT" ls-files)
    source_label='tracked source'
else
    mapfile -d '' -t candidates < <(
        find . \
            -path './.git' -prune -o \
            -type f -print0
    )
    source_label='source archive'
fi

for raw_path in "${candidates[@]}"; do
    path="${raw_path#./}"
    ((checked += 1))
    if is_forbidden_path "$path"; then
        violations+=("$path")
    fi
done

if (( ${#violations[@]} > 0 )); then
    printf 'ERROR: generated/runtime artifacts are present in %s:\n' "$source_label" >&2
    printf '  %s\n' "${violations[@]}" >&2
    exit 1
fi

printf '[KAORI hygiene] %s is clean (%s files checked).\n' "$source_label" "$checked"
