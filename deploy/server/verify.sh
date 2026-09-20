#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
SERVER_COMPOSE="${KAORI_SERVER_COMPOSE:-$SCRIPT_DIR/compose.server.yml}"
KAORI_DEPLOY_ENV_FILE="${KAORI_DEPLOY_ENV_FILE:-/etc/kaori/deploy.env}"
KAORI_APP_ENV_FILE="${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}"
KAORI_SECRETS_ENV_FILE="${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}"
KAORI_RELEASE_ENV_FILE="${KAORI_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}"
KAORI_EXPECTED_IMAGE="${KAORI_EXPECTED_IMAGE:-}"
restart_check=false

fail() {
  printf '❌ KAORI server verification failed · %s\n' "$*" >&2
  exit 1
}

if [[ "${1:-}" == '--restart-check' ]]; then
  restart_check=true
  shift
fi
[[ $# -eq 0 ]] || fail 'usage: verify.sh [--restart-check]'

command -v docker >/dev/null 2>&1 || fail 'docker is required'
[[ -r "$KAORI_DEPLOY_ENV_FILE" ]] || fail "deployment environment is not readable: $KAORI_DEPLOY_ENV_FILE"
set -a
# shellcheck source=/dev/null
source "$KAORI_DEPLOY_ENV_FILE"
set +a
KAORI_APP_ENV_FILE="${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}"
KAORI_SECRETS_ENV_FILE="${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}"
KAORI_RELEASE_ENV_FILE="${KAORI_RELEASE_ENV_FILE:-${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}}"
export KAORI_APP_ENV_FILE KAORI_SECRETS_ENV_FILE KAORI_RELEASE_ENV_FILE

for path in "$KAORI_APP_ENV_FILE" "$KAORI_SECRETS_ENV_FILE" "$KAORI_RELEASE_ENV_FILE"; do
  [[ -r "$path" ]] || fail "runtime environment is not readable: $path"
done

# shellcheck source=deploy/server/release-state.sh
source "$SCRIPT_DIR/release-state.sh"
load_current_release_identity || fail 'current release identity is unavailable'
compose=(docker compose --env-file "$KAORI_DEPLOY_ENV_FILE" -f "$BASE_COMPOSE" -f "$SERVER_COMPOSE")
"${compose[@]}" config --quiet || fail 'Compose configuration is invalid'

application_services=(
  web worker maintenance-worker runtime-worker validation-worker analytics-worker
  reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat
)
services=(postgres redis "${application_services[@]}")

for service in "${services[@]}"; do
  cid="$("${compose[@]}" ps -q "$service")"
  [[ -n "$cid" ]] || fail "$service has no container"
  runtime_status="$(docker inspect --format '{{.State.Status}}' "$cid")"
  [[ "$runtime_status" == 'running' ]] || fail "$service is not running (status=$runtime_status)"
done
printf '✅ Runtime containers running\n'

for service in postgres redis; do
  cid="$("${compose[@]}" ps -q "$service")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$cid")"
  [[ "$health" == 'healthy' ]] || fail "$service is not healthy (health=$health)"
  published_ports="$(docker inspect --format '{{json .NetworkSettings.Ports}}' "$cid")"
  [[ "$published_ports" != *'HostPort'* ]] || fail "$service unexpectedly publishes a host port"
done
printf '✅ PostgreSQL / Redis private and healthy\n'

web_cid="$("${compose[@]}" ps -q web)"
web_ports="$(docker inspect --format '{{json .NetworkSettings.Ports}}' "$web_cid")"
[[ "$web_ports" != *'HostPort'* ]] || fail 'web unexpectedly publishes a host port'
printf '✅ KAORI web is Docker-network only\n'

docker network inspect edge-public >/dev/null 2>&1 || fail 'shared edge network edge-public is missing'
web_networks="$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$web_cid")"
[[ "$web_networks" == *'"edge-public"'* ]] || fail 'web is not attached to shared edge network edge-public'
web_edge_aliases="$(docker inspect --format '{{json (index .NetworkSettings.Networks "edge-public").Aliases}}' "$web_cid")"
[[ "$web_edge_aliases" == *'"kaori-web"'* ]] || fail 'web is missing stable shared-edge alias kaori-web'

private_services=(postgres redis worker maintenance-worker runtime-worker validation-worker analytics-worker reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat)
for service in "${private_services[@]}"; do
  cid="$("${compose[@]}" ps -q "$service")"
  service_networks="$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$cid")"
  [[ "$service_networks" != *'"edge-public"'* ]] || fail "$service must not join shared edge network edge-public"
done
printf '✅ Shared edge network isolation PASS\n'

if [[ -n "$KAORI_EXPECTED_IMAGE" ]]; then
  [[ "$KAORI_EXPECTED_IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'KAORI_EXPECTED_IMAGE must be immutable'
  for service in "${application_services[@]}"; do
    cid="$("${compose[@]}" ps -q "$service")"
    configured_image="$(docker inspect --format '{{.Config.Image}}' "$cid")"
    [[ "$configured_image" == "$KAORI_EXPECTED_IMAGE" ]] || fail "$service is not running expected immutable image"
  done
  printf '🐳 Immutable application image PASS\n'
fi

beat_count="$("${compose[@]}" ps -q beat | sed '/^$/d' | wc -l | tr -d ' ')"
[[ "$beat_count" == '1' ]] || fail "expected exactly one Beat container, found $beat_count"

active_queues() {
  local service="$1"
  local cid
  cid="$("${compose[@]}" ps -q "$service")"
  docker exec "$cid" sh -ec 'celery --app celery_worker:celery_app inspect active_queues --timeout=10' 2>/dev/null || return 1
}

for service in worker maintenance-worker runtime-worker validation-worker analytics-worker reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker; do
  active_queues "$service" >/dev/null || fail "$service did not report active_queues"
done
printf '✅ Worker queues and Beat PASS\n'

"${compose[@]}" exec -T web python -c \
  "import urllib.request; request = urllib.request.Request('http://127.0.0.1:5000/health/ready', headers={'Host': 'localhost'}); urllib.request.urlopen(request, timeout=10).read()" \
  >/dev/null || fail 'internal web readiness failed inside the web container'
printf '🩺 Internal web:5000 readiness PASS\n'

if [[ "$restart_check" == 'true' ]]; then
  restart_before="$(docker inspect --format '{{.RestartCount}}' "$web_cid")"
  sleep 2
  restart_after="$(docker inspect --format '{{.RestartCount}}' "$web_cid")"
  [[ "$restart_after" == "$restart_before" ]] || fail 'web container restarted during verification window'
fi

printf '\n✅ KAORI internal server verification PASS\n'
