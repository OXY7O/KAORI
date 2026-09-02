#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
KAORI_ENV_FILE="${KAORI_ENV_FILE:-/etc/kaori/.env.production}"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
VPS_COMPOSE="${KAORI_VPS_COMPOSE:-$SCRIPT_DIR/compose.vps.yml}"
KAORI_BACKUP_DIR="${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}"

fail() {
  printf 'KAORI VPS restore failed: %s\n' "$*" >&2
  exit 1
}

[[ $# -eq 1 ]] || fail 'usage: restore.sh /var/lib/kaori/backups/kaori-postgres-*.dump'
command -v readlink >/dev/null 2>&1 || fail 'readlink is required'
command -v docker >/dev/null 2>&1 || fail 'docker is required'
command -v sha256sum >/dev/null 2>&1 || fail 'sha256sum is required'
[[ -r "$KAORI_ENV_FILE" ]] || fail "environment file is not readable: $KAORI_ENV_FILE"

backup_root="$(readlink -f "$KAORI_BACKUP_DIR")"
backup_file="$(readlink -f "$1")"
[[ -n "$backup_file" && -f "$backup_file" && -s "$backup_file" ]] || fail 'backup must be an existing non-empty regular file'
case "$backup_file" in
  "$backup_root"/*) ;;
  *) fail "backup must reside under $backup_root" ;;
esac
[[ -f "$backup_file.sha256" ]] || fail 'backup checksum file is required'
(
  cd -- "$(dirname -- "$backup_file")"
  sha256sum --check "$(basename -- "$backup_file.sha256")"
) || fail 'backup checksum validation failed'

compose=(docker compose --env-file "$KAORI_ENV_FILE" -f "$BASE_COMPOSE" -f "$VPS_COMPOSE")
application_services=(
  web worker maintenance-worker runtime-worker validation-worker analytics-worker
  reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat
)

stop_application_services() {
  "${compose[@]}" stop "${application_services[@]}"
}

stop_application_services
"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' \
  < "$backup_file"

printf 'Restore completed from %s\n' "$backup_file"
