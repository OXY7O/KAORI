#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
KAORI_ENV_FILE="${KAORI_ENV_FILE:-/etc/kaori/.env.production}"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
VPS_COMPOSE="${KAORI_VPS_COMPOSE:-$SCRIPT_DIR/compose.vps.yml}"
READY_URL="${KAORI_READY_URL:-http://127.0.0.1:5000/health/ready}"

fail() {
  printf 'KAORI VPS verification failed: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail 'docker is required'
command -v curl >/dev/null 2>&1 || fail 'curl is required'
[[ -r "$KAORI_ENV_FILE" ]] || fail "environment file is not readable: $KAORI_ENV_FILE"

compose=(docker compose --env-file "$KAORI_ENV_FILE" -f "$BASE_COMPOSE" -f "$VPS_COMPOSE")
services=(
  postgres
  redis
  web
  worker
  maintenance-worker
  runtime-worker
  validation-worker
  analytics-worker
  reports-worker
  forecasting-worker
  resolver-execution-worker
  resolver-maintenance-worker
  beat
)

for service in "${services[@]}"; do
  cid="$("${compose[@]}" ps -q "$service")"
  [[ -n "$cid" ]] || fail "$service has no container"
  status="$(docker inspect --format '{{.State.Status}}' "$cid")"
  [[ "$status" == 'running' ]] || fail "$service is not running (status=$status)"
done

for service in postgres redis; do
  cid="$("${compose[@]}" ps -q "$service")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$cid")"
  [[ "$health" == 'healthy' ]] || fail "$service is not healthy (health=$health)"
done

beat_count="$("${compose[@]}" ps -q beat | sed '/^$/d' | wc -l | tr -d ' ')"
[[ "$beat_count" == '1' ]] || fail "expected exactly one Beat container, found $beat_count"

curl --fail --silent --show-error --max-time 10 "$READY_URL" >/dev/null || \
  fail "loopback readiness failed: $READY_URL"

printf 'KAORI VPS verification PASS: %s\n' "$READY_URL"
