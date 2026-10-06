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

"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
  > "$backup_file"

[[ -s "$backup_file" ]] || fail 'pg_dump produced an empty backup'
sha256sum "$backup_file" > "$backup_file.sha256"
chmod 0600 "$backup_file" "$backup_file.sha256"
printf '%s\n' "$backup_file"
