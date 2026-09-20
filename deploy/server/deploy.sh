#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
SERVER_COMPOSE="${KAORI_SERVER_COMPOSE:-$SCRIPT_DIR/compose.server.yml}"
KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"
KAORI_BACKUP_DIR="${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}"
KAORI_DEPLOY_ENV_FILE="${KAORI_DEPLOY_ENV_FILE:-/etc/kaori/deploy.env}"
KAORI_APP_ENV_FILE="${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}"
KAORI_SECRETS_ENV_FILE="${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}"
active_release_env="${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}"
candidate_release_env="$KAORI_STATE_DIR/candidate-release.env"

fail() {
  printf '❌ KAORI server deployment failed · %s\n' "$*" >&2
  exit 1
}

status() {
  local icon="$1"
  shift
  printf '%s %s\n' "$icon" "$*"
}

[[ $# -eq 3 ]] || fail 'usage: deploy.sh IMAGE@sha256:<digest> SOURCE_SHA RELEASE_VERSION'
image="$1"
source_sha="$2"
release_version="$3"

[[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'application image must be digest-qualified'
[[ "$image" == */* ]] || fail 'application image must include an explicit registry host'
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'source SHA must be exactly 40 lowercase hex characters'
[[ "$release_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || fail 'release version must be vX.Y.Z or vX.Y.Z-rc.N'
app_version="${release_version#v}"

for command_name in docker curl stat mktemp sort sed head; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"
done

[[ -r "$KAORI_DEPLOY_ENV_FILE" ]] || fail "deployment environment is not readable: $KAORI_DEPLOY_ENV_FILE"
set -a
# shellcheck source=/dev/null
source "$KAORI_DEPLOY_ENV_FILE"
set +a

KAORI_APP_ENV_FILE="${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}"
KAORI_SECRETS_ENV_FILE="${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}"
active_release_env="${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}"
export KAORI_APP_ENV_FILE KAORI_SECRETS_ENV_FILE

for path in "$KAORI_APP_ENV_FILE" "$KAORI_SECRETS_ENV_FILE" "$KAORI_DEPLOY_ENV_FILE"; do
  [[ -f "$path" && ! -L "$path" && -r "$path" ]] || fail "runtime environment must be a readable regular non-symlink file: $path"
done
[[ "$(stat -c '%a' "$KAORI_SECRETS_ENV_FILE")" == '600' ]] || fail 'secrets.env must use mode 600'
for path in "$KAORI_APP_ENV_FILE" "$KAORI_DEPLOY_ENV_FILE"; do
  mode="$(stat -c '%a' "$path")"
  [[ "$mode" == '600' || "$mode" == '640' ]] || fail "$path must use mode 600 or 640"
done

[[ -f "$BASE_COMPOSE" ]] || fail "base Compose file is missing: $BASE_COMPOSE"
[[ -f "$SERVER_COMPOSE" ]] || fail "server Compose overlay is missing: $SERVER_COMPOSE"

docker info >/dev/null 2>&1 || fail 'Docker daemon is not reachable by the deploy user'
compose_version="$(docker compose version --short | sed -E 's/^v//; s/[^0-9.].*$//')"
[[ "$compose_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "unable to parse Docker Compose version: $compose_version"
minimum_compose='2.24.4'
oldest="$(printf '%s\n%s\n' "$minimum_compose" "$compose_version" | sort -V | head -n1)"
[[ "$oldest" == "$minimum_compose" ]] || fail "Docker Compose $minimum_compose or newer is required for !reset/!override; found $compose_version"
status '✅' "Compose capability PASS · $compose_version ≥ 2.24.4"

: "${KAORI_PUBLIC_DOMAIN:?Set KAORI_PUBLIC_DOMAIN in /etc/kaori/deploy.env}"
[[ "$KAORI_PUBLIC_DOMAIN" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]] || fail 'KAORI_PUBLIC_DOMAIN is invalid'

validate_image_pin() {
  local name="$1"
  local value="${!name:-}"
  [[ "$value" =~ @sha256:[0-9a-f]{64}$ ]] || fail "$name must be an immutable digest-qualified image"
}
for image_var in KAORI_POSTGRES_IMAGE KAORI_REDIS_IMAGE; do
  validate_image_pin "$image_var"
done

umask 077
mkdir -p "$KAORI_STATE_DIR" "$KAORI_BACKUP_DIR" "$(dirname -- "$active_release_env")"

registry_user=''
registry_password=''
IFS= read -r registry_user || fail 'registry username was not supplied on stdin'
IFS= read -r registry_password || fail 'registry password was not supplied on stdin'
[[ -n "$registry_user" ]] || fail 'registry username is empty'
[[ -n "$registry_password" ]] || fail 'registry password is empty'

registry_host="${image%%/*}"
DOCKER_CONFIG="$(mktemp -d)"
export DOCKER_CONFIG
committed=false
cleanup() {
  registry_password=''
  rm -rf -- "$DOCKER_CONFIG"
  [[ "$committed" == 'true' ]] || rm -f -- "$candidate_release_env"
}
trap cleanup EXIT INT TERM HUP

status '🔐' "Registry authentication · $registry_host"
printf '%s\n' "$registry_password" | docker login "$registry_host" --username "$registry_user" --password-stdin >/dev/null
registry_password=''
status '🐳' 'Pulling immutable KAORI candidate'
docker pull "$image" >/dev/null
image_revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image")"
[[ "$image_revision" == "$source_sha" ]] || fail "image revision does not match requested source SHA (image=$image_revision source=$source_sha)"
image_created="$(docker image inspect --format '{{.Created}}' "$image")"
[[ -n "$image_created" ]] || fail 'image creation timestamp is missing'

cat > "$candidate_release_env" <<EOF
KAORI_IMAGE=$image
APP_VERSION=$app_version
APP_BUILD_SHA=$source_sha
APP_BUILD_DATE=$image_created
EOF
chmod 600 "$candidate_release_env"
export KAORI_RELEASE_ENV_FILE="$candidate_release_env"
export KAORI_IMAGE="$image"
export APP_VERSION="$app_version"
export APP_BUILD_SHA="$source_sha"
export APP_BUILD_DATE="$image_created"
export KAORI_BACKUP_DIR
export KAORI_SERVER_COMPOSE="$SERVER_COMPOSE"

compose=(docker compose --env-file "$KAORI_DEPLOY_ENV_FILE" -f "$BASE_COMPOSE" -f "$SERVER_COMPOSE")
"${compose[@]}" config --quiet || fail 'Compose configuration validation failed'
status '✅' 'Compose render PASS'

status '🐳' 'Pulling immutable infrastructure images'
"${compose[@]}" pull postgres redis >/dev/null

wait_healthy() {
  local service="$1"
  local deadline=$(( $(date +%s) + 180 ))
  local cid health
  while (( $(date +%s) < deadline )); do
    cid="$("${compose[@]}" ps -q "$service")"
    if [[ -n "$cid" ]]; then
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
      [[ "$health" == 'healthy' ]] && return 0
      [[ "$health" == 'unhealthy' || "$health" == 'exited' || "$health" == 'dead' ]] && fail "$service entered terminal state: $health"
    fi
    sleep 3
  done
  fail "$service did not become healthy before timeout"
}

status '🚀' 'Starting PostgreSQL and Redis'
"${compose[@]}" up -d --pull never postgres redis
wait_healthy postgres
wait_healthy redis
status '✅' 'PostgreSQL / Redis healthy'

backup_path='none'
has_existing_state="$(
  "${compose[@]}" exec -T postgres sh -ec \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname NOT IN ('\''pg_catalog'\'', '\''information_schema'\''));"' |
    tr -d '[:space:]'
)"
if [[ "$has_existing_state" == 't' ]]; then
  status '💾' 'Creating pre-migration PostgreSQL backup'
  backup_path="$(bash "$SCRIPT_DIR/backup.sh")"
  [[ -n "$backup_path" && -s "$backup_path" ]] || fail 'pre-migration backup was not created successfully'
  status '✅' "Backup PASS · $backup_path"
else
  status '💾' 'Backup not required · database has no user tables'
fi

status '🔎' 'Validating portable KAORI runtime configuration'
"${compose[@]}" run --rm --pull never validate
status '✅' 'Application configuration PASS'

status '🗃️' 'Running database migrations'
"${compose[@]}" run --rm --pull never migrate
status '✅' 'Database migration PASS'

application_services=(
  web worker maintenance-worker runtime-worker validation-worker analytics-worker
  reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat
)
status '🚀' 'Starting KAORI application services'
"${compose[@]}" up -d --pull never "${application_services[@]}"
KAORI_EXPECTED_IMAGE="$image" bash "$SCRIPT_DIR/verify.sh" --restart-check
status '✅' 'Internal runtime PASS'

status '🌐' 'Verifying public HTTPS readiness through shared edge'
https_deadline=$(( $(date +%s) + 180 ))
while (( $(date +%s) < https_deadline )); do
  if curl --fail --silent --show-error --max-time 10 "https://$KAORI_PUBLIC_DOMAIN/health/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
curl --fail --silent --show-error --max-time 10 "https://$KAORI_PUBLIC_DOMAIN/health/ready" >/dev/null || \
  fail 'public HTTPS readiness through shared edge did not become healthy before timeout'
status '✅' 'Public HTTPS readiness through shared edge PASS'

if [[ -f "$KAORI_STATE_DIR/current-image" ]]; then
  cp -- "$KAORI_STATE_DIR/current-image" "$KAORI_STATE_DIR/previous-image"
fi
if [[ -f "$KAORI_STATE_DIR/source-sha" ]]; then
  cp -- "$KAORI_STATE_DIR/source-sha" "$KAORI_STATE_DIR/previous-source-sha"
fi
if [[ -f "$KAORI_STATE_DIR/current-version" ]]; then
  cp -- "$KAORI_STATE_DIR/current-version" "$KAORI_STATE_DIR/previous-version"
fi
if [[ -f "$KAORI_STATE_DIR/current-build-date" ]]; then
  cp -- "$KAORI_STATE_DIR/current-build-date" "$KAORI_STATE_DIR/previous-build-date"
fi
if [[ -f "$active_release_env" ]]; then
  cp -- "$active_release_env" "$KAORI_STATE_DIR/previous-release.env"
fi
if [[ "$backup_path" != 'none' ]]; then
  printf '%s\n' "$backup_path" > "$KAORI_STATE_DIR/previous-backup"
else
  rm -f -- "$KAORI_STATE_DIR/previous-backup"
fi

printf '%s\n' "$image" > "$KAORI_STATE_DIR/current-image"
printf '%s\n' "$source_sha" > "$KAORI_STATE_DIR/source-sha"
printf '%s\n' "$release_version" > "$KAORI_STATE_DIR/current-version"
printf '%s\n' "$image_created" > "$KAORI_STATE_DIR/current-build-date"
printf '%s\n' "$backup_path" > "$KAORI_STATE_DIR/pre-migration-backup"
printf '%s\n' 'pass' > "$KAORI_STATE_DIR/migration-result"
printf '%s\n' 'pass' > "$KAORI_STATE_DIR/verification-result"
date -u +%Y-%m-%dT%H:%M:%SZ > "$KAORI_STATE_DIR/deployed-at"
chmod 600 "$KAORI_STATE_DIR"/*
mv -- "$candidate_release_env" "$active_release_env"
chmod 600 "$active_release_env"
committed=true

printf '\n✅ KAORI UAT deployment PASS\n'
printf '📦 Release  %s\n' "$release_version"
printf '🔎 SHA      %s\n' "$source_sha"
printf '🐳 Image    %s\n' "$image"
printf '🌐 URL      https://%s\n' "$KAORI_PUBLIC_DOMAIN"
printf '🔒 TLS      PASS\n'
printf '💾 Backup   %s\n' "$backup_path"
