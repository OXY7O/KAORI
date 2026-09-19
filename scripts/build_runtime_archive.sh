#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

version="${1:-}"
output="${2:-}"

if [[ ! "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    printf 'FAIL — Runtime Package\n'
    printf '  version  : %s\n' "${version:-missing}"
    printf '  expected : strict SemVer (for example 0.1.1)\n' >&2
    exit 1
fi

output="${output:-dist/kaori-runtime-v${version}.zip}"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
payload="$staging/kaori"
mkdir -p "$payload/scripts" "$(dirname "$output")"

printf '== KAORI Release · Runtime Package ==\n'
printf '  version : v%s\n' "$version"
printf '  output  : %s\n' "$output"

copy_tree() {
    local path="$1"
    [[ -e "$path" ]] || {
        printf 'FAIL — required runtime path missing: %s\n' "$path" >&2
        exit 1
    }
    cp -a "$path" "$payload/$(dirname "$path")/"
}

copy_file() {
    local path="$1"
    [[ -f "$path" ]] || {
        printf 'FAIL — required runtime file missing: %s\n' "$path" >&2
        exit 1
    }
    mkdir -p "$payload/$(dirname "$path")"
    cp "$path" "$payload/$path"
}

copy_tree app
copy_tree migrations
copy_file run.py
copy_file celery_worker.py
copy_file gunicorn.conf.py
copy_file requirements/base.txt
copy_file docker/entrypoint.sh
copy_file scripts/wait_for_db.py
copy_file scripts/validate_production_env.py

python - "$payload" "$output" <<'PY'
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import sys

payload = Path(sys.argv[1])
output = Path(sys.argv[2])
forbidden = (
    '/tests/', '/example/', '/.github/', '/docs/', '/.devcontainer/', '/.vscode/',
    '__pycache__', '.pytest_cache', '.ruff_cache', 'node_modules', '.env',
)
with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
    for path in sorted(payload.rglob('*')):
        if path.is_file():
            name = path.relative_to(payload.parent).as_posix()
            if any(token in f'/{name}' for token in forbidden):
                raise SystemExit(f'forbidden runtime artifact path: {name}')
            archive.write(path, name)
with ZipFile(output) as archive:
    names = archive.namelist()
    if not any(name.startswith('kaori/app/') for name in names):
        raise SystemExit('runtime archive is missing application package')
    if not any(name.startswith('kaori/migrations/') for name in names):
        raise SystemExit('runtime archive is missing migrations')
print(f'PASS — runtime package contains {len(names)} application files')
PY

printf 'PASS — Runtime Package\n'
printf '  artifact : %s\n' "$output"
printf '  boundary : application-only\n'
