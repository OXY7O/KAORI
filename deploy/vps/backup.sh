#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
KAORI_ENV_FILE="${KAORI_ENV_FILE:-/etc/kaori/.env.production}"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
VPS_COMPOSE="${KAORI_VPS_COMPOSE:-$SCRIPT_DIR/compose.vps.yml}"
KAORI_BACKUP_DIR="${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}"

fail() {
  printf 'KAORI VPS backup failed: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail 'docker is required'
command -v sha256sum >/dev/null 2>&1 || fail 'sha256sum is required'
[[ -r "$KAORI_ENV_FILE" ]] || fail "environment file is not readable: $KAORI_ENV_FILE"

umask 077
mkdir -p "$KAORI_BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$KAORI_BACKUP_DIR/kaori-postgres-$timestamp.dump"
compose=(docker compose --env-file "$KAORI_ENV_FILE" -f "$BASE_COMPOSE" -f "$VPS_COMPOSE")

"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
  > "$backup_file"

[[ -s "$backup_file" ]] || fail 'pg_dump produced an empty backup'
sha256sum "$backup_file" > "$backup_file.sha256"
chmod 600 "$backup_file" "$backup_file.sha256"
printf '%s\n' "$backup_file"
