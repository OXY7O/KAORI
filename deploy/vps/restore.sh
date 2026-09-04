#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
VPS_COMPOSE="${KAORI_VPS_COMPOSE:-$SCRIPT_DIR/compose.vps.yml}"
KAORI_DEPLOY_ENV_FILE="${KAORI_DEPLOY_ENV_FILE:-/etc/kaori/deploy.env}"
KAORI_BACKUP_DIR="${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}"

fail() {
  printf 'KAORI VPS restore failed: %s\n' "$*" >&2
  exit 1
}

[[ $# -eq 1 ]] || fail 'usage: restore.sh /var/lib/kaori/backups/kaori-postgres-*.dump'
for command_name in readlink docker sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"
done
[[ -r "$KAORI_DEPLOY_ENV_FILE" ]] || fail "deployment environment is not readable: $KAORI_DEPLOY_ENV_FILE"
set -a
# shellcheck source=/dev/null
source "$KAORI_DEPLOY_ENV_FILE"
set +a
KAORI_APP_ENV_FILE="${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}"
KAORI_SECRETS_ENV_FILE="${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}"
KAORI_RELEASE_ENV_FILE="${KAORI_RELEASE_ENV_FILE:-${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}}"
export KAORI_APP_ENV_FILE KAORI_SECRETS_ENV_FILE KAORI_RELEASE_ENV_FILE

# shellcheck source=deploy/vps/release-state.sh
source "$SCRIPT_DIR/release-state.sh"
load_current_release_identity || fail 'current release identity is unavailable; restore requires recorded deployment state'

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

compose=(docker compose --env-file "$KAORI_DEPLOY_ENV_FILE" -f "$BASE_COMPOSE" -f "$VPS_COMPOSE")
application_services=(
  web worker maintenance-worker runtime-worker validation-worker analytics-worker
  reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat nginx certbot
)

"${compose[@]}" stop "${application_services[@]}"
"${compose[@]}" exec -T postgres sh -ec \
  'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' \
  < "$backup_file"

printf 'Restore completed from %s\n' "$backup_file"
