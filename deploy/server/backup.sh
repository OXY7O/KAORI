#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
SERVER_COMPOSE="${KAORI_SERVER_COMPOSE:-$SCRIPT_DIR/compose.server.yml}"
KAORI_DEPLOY_ENV_FILE="${KAORI_DEPLOY_ENV_FILE:-/etc/kaori/deploy.env}"
KAORI_BACKUP_DIR="${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}"

fail() {
  printf 'KAORI server backup failed: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail 'docker is required'
command -v sha256sum >/dev/null 2>&1 || fail 'sha256sum is required'
[[ -r "$KAORI_DEPLOY_ENV_FILE" ]] || fail "deployment environment is not readable: $KAORI_DEPLOY_ENV_FILE"
set -a
# shellcheck source=/dev/null
source "$KAORI_DEPLOY_ENV_FILE"
set +a
KAORI_APP_ENV_FILE="${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}"
KAORI_SECRETS_ENV_FILE="${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}"
KAORI_RELEASE_ENV_FILE="${KAORI_RELEASE_ENV_FILE:-${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}}"
export KAORI_APP_ENV_FILE KAORI_SECRETS_ENV_FILE KAORI_RELEASE_ENV_FILE

# shellcheck source=deploy/server/release-state.sh
source "$SCRIPT_DIR/release-state.sh"
load_current_release_identity || fail 'current release identity is unavailable; complete one governed deployment first'

umask 077
mkdir -p "$KAORI_BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$KAORI_BACKUP_DIR/kaori-postgres-$timestamp.dump"
compose=(docker compose --env-file "$KAORI_DEPLOY_ENV_FILE" -f "$BASE_COMPOSE" -f "$SERVER_COMPOSE")

printf '⏳ UAT backup · creating consistent custom-format PostgreSQL archive\n' >&2
"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
  > "$backup_file"

[[ -s "$backup_file" ]] || fail 'pg_dump produced an empty backup'
printf '✅ UAT backup · PostgreSQL archive created\n' >&2

# Ownership/schema evidence is retained separately from the no-owner restore
# archive, with the same restricted filesystem protections.
printf '⏳ UAT backup · retaining schema ownership evidence (contents private)\n' >&2
"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --schema-only' \
  > "$backup_file.schema.sql"
[[ -s "$backup_file.schema.sql" ]] || fail 'schema ownership evidence is empty'
printf '✅ UAT backup · schema ownership evidence created\n' >&2
# Cluster role inventory is sensitive (password verifiers) and needed to
# document post-cutover role recovery. Never print or apply it automatically.
printf '⏳ UAT backup · retaining private PostgreSQL role inventory (no contents logged)\n' >&2
"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_dumpall -U "$POSTGRES_USER" --globals-only' \
  > "$backup_file.roles.sql"
[[ -s "$backup_file.roles.sql" ]] || fail 'global PostgreSQL roles evidence is empty'
printf '✅ UAT backup · private role inventory created\n' >&2
printf '⏳ UAT backup · recording checksums and strict file modes\n' >&2
sha256sum "$backup_file.roles.sql" > "$backup_file.roles.sql.sha256"
chmod 0600 "$backup_file.roles.sql" "$backup_file.roles.sql.sha256"
sha256sum "$backup_file.schema.sql" > "$backup_file.schema.sql.sha256"
chmod 0600 "$backup_file.schema.sql" "$backup_file.schema.sql.sha256"
sha256sum "$backup_file" > "$backup_file.sha256"
chmod 0600 "$backup_file" "$backup_file.sha256"
printf '✅ UAT backup · archive, schema and role checksum evidence PASS\n' >&2
# stdout is a single machine-readable path consumed by deploy.sh.
printf '%s\n' "$backup_file"
