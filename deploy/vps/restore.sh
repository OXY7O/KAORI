#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
KAORI_ENV_FILE="${KAORI_ENV_FILE:-/etc/kaori/.env.production}"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
VPS_COMPOSE="${KAORI_VPS_COMPOSE:-$SCRIPT_DIR/compose.vps.yml}"

fail() {
  printf 'KAORI VPS restore failed: %s\n' "$*" >&2
  exit 1
}

[[ $# -eq 1 ]] || fail 'usage: restore.sh /path/to/kaori-postgres-*.dump'
backup_file="$1"
[[ -f "$backup_file" ]] || fail "backup does not exist: $backup_file"
[[ -s "$backup_file" ]] || fail "backup is empty: $backup_file"
[[ -r "$KAORI_ENV_FILE" ]] || fail "environment file is not readable: $KAORI_ENV_FILE"
command -v docker >/dev/null 2>&1 || fail 'docker is required'
command -v sha256sum >/dev/null 2>&1 || fail 'sha256sum is required'

if [[ -f "$backup_file.sha256" ]]; then
  (
    cd -- "$(dirname -- "$backup_file")"
    sha256sum --check "$(basename -- "$backup_file.sha256")"
  ) || fail 'backup checksum validation failed'
fi

compose=(docker compose --env-file "$KAORI_ENV_FILE" -f "$BASE_COMPOSE" -f "$VPS_COMPOSE")
"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
  < "$backup_file"

printf 'Restore completed from %s\n' "$backup_file"
