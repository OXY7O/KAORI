#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
KAORI_ENV_FILE="${KAORI_ENV_FILE:-/etc/kaori/.env.production}"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
VPS_COMPOSE="${KAORI_VPS_COMPOSE:-$SCRIPT_DIR/compose.vps.yml}"
KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"
KAORI_BACKUP_DIR="${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}"

fail() {
  printf 'KAORI VPS deployment failed: %s\n' "$*" >&2
  exit 1
}

[[ $# -eq 3 ]] || fail 'usage: deploy.sh IMAGE@sha256:<digest> SOURCE_SHA RELEASE_VERSION'
image="$1"
source_sha="$2"
release_version="$3"

[[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'image must be digest-qualified with @sha256:<64 lowercase hex>'
[[ "$image" == */* ]] || fail 'image must include an explicit registry host'
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'source SHA must be exactly 40 lowercase hex characters'
[[ "$release_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || \
  fail 'release version must be a governed vX.Y.Z or vX.Y.Z-rc.N identity'
[[ -r "$KAORI_ENV_FILE" ]] || fail "environment file is not readable: $KAORI_ENV_FILE"
[[ -f "$BASE_COMPOSE" ]] || fail "base Compose file is missing: $BASE_COMPOSE"
[[ -f "$VPS_COMPOSE" ]] || fail "VPS Compose overlay is missing: $VPS_COMPOSE"

for command_name in docker curl stat mktemp; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"
done

env_mode="$(stat -c '%a' "$KAORI_ENV_FILE")"
[[ "$env_mode" == '600' ]] || fail "environment file must use mode 600, found $env_mode"
docker info >/dev/null 2>&1 || fail 'Docker daemon is not reachable by the deploy user'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose plugin is required'

umask 077
mkdir -p "$KAORI_STATE_DIR" "$KAORI_BACKUP_DIR"

registry_user=''
registry_password=''
IFS= read -r registry_user || fail 'registry username was not supplied on stdin'
IFS= read -r registry_password || fail 'registry password was not supplied on stdin'
[[ -n "$registry_user" ]] || fail 'registry username is empty'
[[ -n "$registry_password" ]] || fail 'registry password is empty'

registry_host="${image%%/*}"
DOCKER_CONFIG="$(mktemp -d)"
export DOCKER_CONFIG
cleanup() {
  registry_password=''
  rm -rf -- "$DOCKER_CONFIG"
}
trap cleanup EXIT INT TERM HUP

printf '%s\n' "$registry_password" | docker login "$registry_host" --username "$registry_user" --password-stdin >/dev/null
registry_password=''
docker pull "$image" >/dev/null
image_revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image")"
[[ "$image_revision" == "$source_sha" ]] || fail "image revision label does not match requested source SHA (image=$image_revision source=$source_sha)"
image_created="$(docker image inspect --format '{{.Created}}' "$image")"
[[ -n "$image_created" ]] || fail 'image creation timestamp is missing from immutable image metadata'

# Release identity is supplied by the governed deployment transaction. The
# persistent server environment contains long-lived configuration/secrets and
# is never rewritten merely because the application release changes.
export KAORI_IMAGE="$image"
export APP_VERSION="$release_version"
export APP_BUILD_SHA="$source_sha"
export APP_BUILD_DATE="$image_created"
export KAORI_ENV_FILE
export KAORI_BACKUP_DIR

compose=(docker compose --env-file "$KAORI_ENV_FILE" -f "$BASE_COMPOSE" -f "$VPS_COMPOSE")
"${compose[@]}" config --quiet || fail 'Compose configuration validation failed'

wait_healthy() {
  local service="$1"
  local deadline=$(( $(date +%s) + 180 ))
  local cid health
  while (( $(date +%s) < deadline )); do
    cid="$("${compose[@]}" ps -q "$service")"
    if [[ -n "$cid" ]]; then
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
      [[ "$health" == 'healthy' ]] && return 0
      [[ "$health" == 'unhealthy' || "$health" == 'exited' || "$health" == 'dead' ]] && fail "$service entered terminal health state: $health"
    fi
    sleep 3
  done
  fail "$service did not become healthy before timeout"
}

start_dependencies() {
  "${compose[@]}" pull postgres redis
  "${compose[@]}" up -d --pull never postgres redis
}

wait_for_dependencies() {
  wait_healthy postgres
  wait_healthy redis
}

backup_path='none'
existing_database_requires_backup() {
  local has_existing_state
  has_existing_state="$(
    "${compose[@]}" exec -T postgres sh -ec \
      'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname NOT IN ('\''pg_catalog'\'', '\''information_schema'\''));"' |
      tr -d '[:space:]'
  )"
  if [[ "$has_existing_state" == 't' ]]; then
    backup_path="$(bash "$SCRIPT_DIR/backup.sh")"
    [[ -n "$backup_path" && -s "$backup_path" ]] || fail 'pre-migration backup was not created successfully'
  fi
}

run_validate() {
  "${compose[@]}" run --rm --pull never validate
}

run_migrate() {
  "${compose[@]}" run --rm --pull never migrate
}

application_services=(
  web worker maintenance-worker runtime-worker validation-worker analytics-worker
  reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat
)
start_application_services() {
  "${compose[@]}" up -d --remove-orphans --pull never "${application_services[@]}"
}

run_verify() {
  KAORI_EXPECTED_IMAGE="$image" bash "$SCRIPT_DIR/verify.sh" --restart-check
}

record_deployment() {
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
}

start_dependencies
wait_for_dependencies
existing_database_requires_backup
run_validate
run_migrate
start_application_services
run_verify
record_deployment

printf 'KAORI VPS deployment PASS\n'
printf 'source_sha=%s\n' "$source_sha"
printf 'release_version=%s\n' "$release_version"
printf 'current_image=%s\n' "$image"
printf 'app_build_date=%s\n' "$image_created"
printf 'pre_migration_backup=%s\n' "$backup_path"
