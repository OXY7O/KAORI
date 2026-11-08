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
KAORI_POSTGRES_ADMIN_ENV_FILE="${KAORI_POSTGRES_ADMIN_ENV_FILE:-/etc/kaori/postgres-admin.env}"
KAORI_POSTGRES_MIGRATION_ENV_FILE="${KAORI_POSTGRES_MIGRATION_ENV_FILE:-/etc/kaori/postgres-migrate.env}"
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
deployment_started="$(date +%s)"
status '⏳' 'UAT host deployment · validating immutable release and deployment prerequisites'

[[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'application image must be digest-qualified'
[[ "$image" == */* ]] || fail 'application image must include an explicit registry host'
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'source SHA must be exactly 40 lowercase hex characters'
[[ "$release_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || fail 'release version must be vX.Y.Z or vX.Y.Z-rc.N'
app_version="${release_version#v}"

for command_name in docker curl stat grep sha256sum mktemp sort sed head; do
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
export KAORI_APP_ENV_FILE KAORI_SECRETS_ENV_FILE KAORI_POSTGRES_ADMIN_ENV_FILE KAORI_POSTGRES_MIGRATION_ENV_FILE

for path in "$KAORI_APP_ENV_FILE" "$KAORI_SECRETS_ENV_FILE" "$KAORI_DEPLOY_ENV_FILE"; do
  [[ -f "$path" && ! -L "$path" && -r "$path" ]] || fail "runtime environment must be a readable regular non-symlink file: $path"
done
for path in "$KAORI_POSTGRES_ADMIN_ENV_FILE" "$KAORI_POSTGRES_MIGRATION_ENV_FILE"; do
  [[ -f "$path" && ! -L "$path" && -r "$path" ]] || fail "PostgreSQL credential must be a readable regular non-symlink file: $path"
  [[ "$(stat -c '%a' "$path")" == '600' ]] || fail "PostgreSQL credential file must have mode 600: $path"
done
# Never allow privileged PostgreSQL secrets to leak via shared application files.
for path in "$KAORI_APP_ENV_FILE" "$KAORI_SECRETS_ENV_FILE"; do
  if grep -Eq '^[[:space:]]*(POSTGRES_PASSWORD|KAORI_DB_MIGRATION_URL|KAORI_MIGRATOR_PASSWORD)=' "$path"; then
    fail "privileged PostgreSQL secrets found in shared runtime file: $path"
  fi
done
grep -Eq '^POSTGRES_PASSWORD=.+$' "$KAORI_POSTGRES_ADMIN_ENV_FILE" || fail 'PostgreSQL admin credential not provisioned'
grep -Eq '^KAORI_DB_MIGRATION_URL=.+$' "$KAORI_POSTGRES_MIGRATION_ENV_FILE" || fail 'PostgreSQL migration credential not provisioned'
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
status '⏳' 'UAT host deployment · validating registry/image authority and environment boundaries'

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
status '✅' 'Immutable candidate image pull PASS'
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

application_services=(
  web worker registry-security-worker maintenance-worker runtime-worker validation-worker analytics-worker
  reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat
)
backup_path='none'
has_existing_state="$(
  "${compose[@]}" exec -T postgres sh -ec \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname <> '\''information_schema'\'' AND left(n.nspname, 3) <> '\''pg_'\'');"' |
    tr -d '[:space:]'
)"
[[ "$has_existing_state" == 't' || "$has_existing_state" == 'f' ]] ||
  fail "database inventory returned an invalid state"
if [[ "${KAORI_BUNDLED_FRESH_BOOTSTRAP:-false}" == 'true' &&
      "${KAORI_BUNDLED_SCHEMA_CUTOVER:-false}" == 'true' ]]; then
  fail 'Fresh bootstrap and existing-schema cutover must not both be enabled'
fi
if [[ "$has_existing_state" == 't' &&
      "${KAORI_BUNDLED_FRESH_BOOTSTRAP:-false}" == 'true' ]]; then
  fail 'Existing schema detected; fresh bootstrap is forbidden'
fi
if [[ "$has_existing_state" == 'f' &&
      "${KAORI_BUNDLED_SCHEMA_CUTOVER:-false}" == 'true' ]]; then
  fail 'No schema exists; existing-schema cutover is forbidden'
fi
# A populated legacy database must never be sent into the new-role
# migration service unless an explicitly authorized cutover is in progress.
# Fail before taking backups, stopping writers or running Alembic. The
# existing role-separated path remains eligible for normal future upgrades.
if [[ "$has_existing_state" == 't' &&
      "${KAORI_BUNDLED_SCHEMA_CUTOVER:-false}" != 'true' ]]; then
  current_db_owner="$(
    "${compose[@]}" exec -T postgres sh -ec \
      'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database();"' |
      tr -d '[:space:]'
  )"
  [[ "$current_db_owner" == 'kaori_migrator' ]] ||
    fail 'Existing PostgreSQL is not owned by kaori_migrator; use a separately admitted existing-schema cutover, never ordinary release migration'
fi

if [[ "$has_existing_state" == 't' &&
      "${KAORI_BUNDLED_SCHEMA_CUTOVER:-false}" == 'true' ]]; then
  # Role-only cutover MUST NOT implicitly run newer Alembic migrations.
  # Compare current version table with the release image's exact Alembic heads
  # BEFORE stopping application writers or modifying any database ownership.
  candidate_heads="$("${compose[@]}" run --rm --pull never --no-deps validate \
    python -c 'from alembic.config import Config; from alembic.script import ScriptDirectory; cfg = Config("/app/migrations/alembic.ini"); cfg.set_main_option("script_location", "/app/migrations"); print(",".join(sorted(ScriptDirectory.from_config(cfg).get_heads())))')"
  existing_heads="$("${compose[@]}" exec -T postgres sh -ec \
    'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT string_agg(version_num, chr(44) ORDER BY version_num) FROM public.alembic_version;"' |
    tr -d '[:space:]')"
  [[ -n "$candidate_heads" && -n "$existing_heads" &&
     "$candidate_heads" == "$existing_heads" ]] ||
    fail 'Schema revision differs from candidate release; separate schema admission required BEFORE existing-role cutover'
  status '✅' "Role cutover schema pin PASS · $existing_heads"
  # Stop all writers before the consistent backup and DDL. Docker Compose stop
  # overrides restart policy and does not remove containers or volumes.
  status '🛑' 'Draining existing application writers for database role cutover'
  "${compose[@]}" stop "${application_services[@]}"
fi
if [[ "$has_existing_state" == 't' ]]; then
  status '💾' 'Creating pre-migration PostgreSQL backup (database payload remains private)'
  backup_path="$(bash "$SCRIPT_DIR/backup.sh")"
  [[ -n "$backup_path" && -s "$backup_path" ]] || fail 'pre-migration backup was not created successfully'
  if [[ "${KAORI_BUNDLED_SCHEMA_CUTOVER:-false}" == 'true' ]]; then
    [[ -f "$backup_path.sha256" && -s "$backup_path.schema.sql" &&
       -f "$backup_path.schema.sql.sha256" &&
       -s "$backup_path.roles.sql" && -f "$backup_path.roles.sql.sha256" ]] ||
      fail 'Cutover requires full database, schema and role backup evidence'
    ( cd -- "$(dirname -- "$backup_path")" &&
      sha256sum -c -- "$(basename -- "$backup_path.sha256")" >/dev/null &&
      sha256sum -c -- "$(basename -- "$backup_path.schema.sql.sha256")" >/dev/null &&
      sha256sum -c -- "$(basename -- "$backup_path.roles.sql.sha256")" >/dev/null
    ) || fail 'Cutover backup checksums did not verify'
    "${compose[@]}" exec -T postgres pg_restore --list < "$backup_path" >/dev/null ||
      fail 'Cutover pg_restore archive could not be inspected'
  fi
  status '✅' "Backup PASS · $backup_path"
else
  status '💾' 'Backup not required · database has no user tables'
fi

status '🔎' 'Validating portable KAORI runtime configuration'
"${compose[@]}" run --rm --pull never validate
status '✅' 'Application configuration PASS'

# Safe first-run: no volume deletion and no legacy object ownership transfer.
# An initialized but empty PostgreSQL volume is supported. Any object/role
# ambiguity causes db-provision to abort before its transactional role DDL.
if [[ "$has_existing_state" == 'f' ]]; then
  [[ "${KAORI_BUNDLED_FRESH_BOOTSTRAP:-false}" == 'true' ]] ||
    fail 'Empty bundled database requires explicit KAORI_BUNDLED_FRESH_BOOTSTRAP=true'
  status '🔐' 'Provisioning role isolation on verified empty bundled database'
  "${compose[@]}" run --rm --pull never db-provision
  status '✅' 'Fresh bundled PostgreSQL role provisioning PASS'
fi

if [[ "$has_existing_state" == 't' &&
      "${KAORI_BUNDLED_SCHEMA_CUTOVER:-false}" == 'true' ]]; then
  status '🔐' 'Applying one-time restricted roles to existing PostgreSQL schema'
  "${compose[@]}" run --rm --pull never db-provision \
    python scripts/server_database_boundary.py cutover
  status '✅' 'Existing-schema PostgreSQL ownership cutover PASS'
fi

status '🗃️' 'Running database migrations'
"${compose[@]}" run --rm --pull never migrate
status '✅' 'Database migration PASS'

# First admin is an application-level operation, never migration DDL.
# Only a proven virgin database with explicit operator opt-in can invoke it.
if [[ "$has_existing_state" == 'f' ]]; then
  status '🔑' 'Initializing first administrator on empty bundled database'
  "${compose[@]}" run --rm --pull never db-bootstrap-admin
  status '✅' 'First administrator bootstrap PASS'
fi

# Refuse to launch web/worker/Beat until the actual runtime ACL is verified.
status '🔒' 'Verifying effective runtime PostgreSQL privileges and immutable ledger'
"${compose[@]}" run --rm --pull never db-verify
status '✅' 'PostgreSQL runtime admission PASS'

status '🚀' 'Starting KAORI application services'
"${compose[@]}" up -d --pull never "${application_services[@]}"
KAORI_EXPECTED_IMAGE="$image" bash "$SCRIPT_DIR/verify.sh" --restart-check
status '✅' 'Internal runtime PASS'

status '✅' 'KAORI application runtime healthy · public publication is an independent operation'
status '⏳' 'UAT host deployment · recording verified immutable release state and rollback pointers'

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
status '✅' 'Verified release state committed; previous release/backup pointers retained where available'
deployment_elapsed=$(( $(date +%s) - deployment_started ))

printf '\n✅ KAORI UAT deployment PASS\n'
printf '📦 Release  %s\n' "$release_version"
printf '🔎 SHA      %s\n' "$source_sha"
printf '🐳 Image    %s\n' "$image"
printf '🩺 Runtime  PASS · internal application health\n'
printf '💾 Backup   %s\n' "$backup_path"
printf '⏱️ Host deployment elapsed %dm %02ds\n' $((deployment_elapsed / 60)) $((deployment_elapsed % 60))
printf 'ℹ️ Public-edge reconciliation and human UAT acceptance are separate gates.\n'
