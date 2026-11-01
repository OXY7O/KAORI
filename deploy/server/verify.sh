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
  web worker registry-security-worker maintenance-worker runtime-worker validation-worker analytics-worker
  reports-worker forecasting-worker resolver-execution-worker resolver-maintenance-worker beat
)
services=(postgres redis "${application_services[@]}")
printf '⏳ UAT verification · checking web, ten workers, Beat, PostgreSQL and Redis container states\n'

for service in "${services[@]}"; do
  cid="$("${compose[@]}" ps -q "$service")"
  [[ -n "$cid" ]] || fail "$service has no container"
  runtime_status="$(docker inspect --format '{{.State.Status}}' "$cid")"
  [[ "$runtime_status" == 'running' ]] || fail "$service is not running (status=$runtime_status)"
done
printf '✅ Runtime containers running\n'

printf '⏳ UAT verification · checking database/cache health and private ports\n'
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


if [[ -n "$KAORI_EXPECTED_IMAGE" ]]; then
  printf '⏳ UAT verification · confirming every application service uses accepted immutable digest\n'
  [[ "$KAORI_EXPECTED_IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'KAORI_EXPECTED_IMAGE must be immutable'
  for service in "${application_services[@]}"; do
    cid="$("${compose[@]}" ps -q "$service")"
    configured_image="$(docker inspect --format '{{.Config.Image}}' "$cid")"
    [[ "$configured_image" == "$KAORI_EXPECTED_IMAGE" ]] || fail "$service is not running expected immutable image"
  done
  printf '🐳 Immutable application image PASS\n'
fi

printf '⏳ UAT verification · checking exact Beat count and ten target worker queues\n'
beat_count="$("${compose[@]}" ps -q beat | sed '/^$/d' | wc -l | tr -d ' ')"
[[ "$beat_count" == '1' ]] || fail "expected exactly one Beat container, found $beat_count"

# Inspect the configured fleet once, and fail closed unless every expected
# worker reports a nonempty queue list. A global inspect from each container
# could pass based on another worker's response and repeats broker broadcasts.
worker_services=(
  worker registry-security-worker maintenance-worker runtime-worker
  validation-worker analytics-worker reports-worker forecasting-worker
  resolver-execution-worker resolver-maintenance-worker
)
expected_nodes=()
probe_cid=""
for service in "${worker_services[@]}"; do
  cid="$("${compose[@]}" ps -q "$service")"
  [[ -n "$cid" ]] || fail "$service has no container for queue inspection"
  [[ -n "$probe_cid" ]] || probe_cid="$cid"
  container_hostname="$(docker inspect --format '{{.Config.Hostname}}' "$cid")"
  [[ "$container_hostname" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] ||
    fail "$service has an invalid container hostname"
  case "$service" in
    worker) node_prefix=inventory ;;
    registry-security-worker) node_prefix=registry-security ;;
    reports-worker) node_prefix=reports ;;
    *) node_prefix=celery ;;
  esac
  expected_nodes+=("$node_prefix@$container_hostname")
done

destination_csv="$(IFS=,; printf '%s' "${expected_nodes[*]}")"
service_csv="$(IFS=,; printf '%s' "${worker_services[*]}")"
if ! queue_response="$(docker exec "$probe_cid" celery --app celery_worker:celery_app inspect \
  --json --timeout=20 --destination="$destination_csv" active_queues 2>/dev/null)"; then
  fail 'targeted Celery active_queues inspection failed'
fi

# The check is intentionally stricter than Celery's CLI exit code: all ten
# individually named workers must reply, each with a valid active queue.
docker exec -i "$probe_cid" python -c '
import json
import sys

expected = sys.argv[1].split(",")
services = sys.argv[2].split(",")
if len(expected) != 10 or len(services) != 10 or len(set(expected)) != len(expected):
    raise SystemExit("duplicate or incomplete expected Celery worker identities")
try:
    actual = json.load(sys.stdin)
except (ValueError, TypeError):
    raise SystemExit("invalid Celery inspect JSON response") from None
if not isinstance(actual, dict):
    raise SystemExit("Celery inspect reply must be a node-keyed object")
for node, service in zip(expected, services, strict=True):
    queues = actual.get(node)
    if not isinstance(queues, list) or not queues:
        raise SystemExit(f"{service} did not report active queues")
    if any(
        not isinstance(queue, dict)
        or not isinstance(queue.get("name"), str)
        or not queue["name"].strip()
        for queue in queues
    ):
        raise SystemExit(f"{service} reported invalid active queues")
' "$destination_csv" "$service_csv" <<<"$queue_response" ||
  fail 'worker queue readiness admission failed'
printf '✅ Worker queues and Beat PASS\n'
# Verify actual database sessions and environment of each running service;
# Compose parity alone is insufficient to establish runtime least privilege.
printf '⏳ UAT verification · checking effective PostgreSQL access for every application service\n'
for service in "${application_services[@]}"; do
  cid="$("${compose[@]}" ps -q "$service")"
  docker exec "$cid" python scripts/server_database_boundary.py runtime >/dev/null ||
    fail "$service failed PostgreSQL runtime identity/immutable-ledger admission"
done
printf '🔒 Every application service has restricted PostgreSQL access PASS\n'


printf '⏳ UAT verification · probing internal web readiness (not public-edge acceptance)\n'
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
