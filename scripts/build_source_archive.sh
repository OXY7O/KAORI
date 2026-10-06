#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .git ]]; then
    printf 'ERROR: build_source_archive.sh must run from a Git checkout.\n' >&2
    exit 1
fi

bash scripts/verify_source_hygiene.sh

if ! git diff --quiet || ! git diff --cached --quiet; then
    printf 'ERROR: source archive requires a clean Git working tree. Commit or stash changes first.\n' >&2
    exit 1
fi

short_sha="$(git rev-parse --short=12 HEAD)"
output="${1:-dist/kaori-source-${short_sha}.zip}"
mkdir -p "$(dirname "$output")"

git archive \
    --format=zip \
    --prefix=kaori/ \
    --output="$output" \
    HEAD

python - "$output" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import sys

archive = Path(sys.argv[1])
forbidden = ('__pycache__/', '.pytest_cache/', '.ruff_cache/', 'node_modules/', 'instance/')
with ZipFile(archive) as payload:
    names = payload.namelist()
    violations = [name for name in names if any(token in name for token in forbidden)]
if violations:
    raise SystemExit(f'Archive contains forbidden generated files: {violations[:10]}')
print(f'[KAORI archive] {archive} contains {len(names)} tracked source entries.')
PY
