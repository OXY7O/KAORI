#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXAMPLE="$ROOT/example"
ENV_FILE="$EXAMPLE/.env"
[[ -f "$ENV_FILE" ]] || ENV_FILE="$EXAMPLE/.env.example"

stage() { printf '\n== %s ==\n' "$1"; }
pass() { printf 'PASS — %s\n' "$1"; }
fail() { printf 'FAIL — %s\n' "$1" >&2; exit 1; }

compose_file() {
  case "$1" in
    all) printf '%s/compose.demo.yml' "$EXAMPLE" ;;
    prometheus|alertmanager|minio|thanos|runner) printf '%s/%s/compose.yml' "$EXAMPLE" "$1" ;;
    *) fail "Unknown example stack '$1'. Use all, prometheus, alertmanager, minio, thanos, or runner." ;;
  esac
}

endpoint() {
  case "$1" in
    prometheus) printf 'http://127.0.0.1:%s/-/ready' "${PROMETHEUS_PORT:-9090}" ;;
    alertmanager) printf 'http://127.0.0.1:%s/-/ready' "${ALERTMANAGER_PORT:-9093}" ;;
    minio) printf 'http://127.0.0.1:%s/minio/health/ready' "${MINIO_API_PORT:-9000}" ;;
    thanos) printf 'http://127.0.0.1:%s/-/ready' "${THANOS_QUERY_PORT:-10902}" ;;
  esac
}

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

command="${1:-}"
stack="${2:-all}"
file="$(compose_file "$stack")"

case "$command" in
  start)
    stage "KAORI Example · Start · $stack"
    docker compose --env-file "$ENV_FILE" -f "$file" up -d
    pass "Compose stack started: $stack"
    ;;
  stop)
    stage "KAORI Example · Stop · $stack"
    docker compose --env-file "$ENV_FILE" -f "$file" down --remove-orphans
    pass "Compose stack stopped: $stack"
    ;;
  reset)
    stage "KAORI Example · Reset · $stack"
    docker compose --env-file "$ENV_FILE" -f "$file" down --volumes --remove-orphans
    pass "Compose stack and demo volumes removed: $stack"
    ;;
  status)
    stage "KAORI Example · Readiness · $stack"
    docker compose --env-file "$ENV_FILE" -f "$file" ps
    if [[ "$stack" == all ]]; then
      checks=(prometheus alertmanager minio thanos)
    elif [[ "$stack" == runner ]]; then
      docker compose --env-file "$ENV_FILE" -f "$file" ps --status running | grep -q runner || fail 'Runner container is not running.'
      pass 'Runner container is running.'
      exit 0
    else
      checks=("$stack")
    fi
    for component in "${checks[@]}"; do
      url="$(endpoint "$component")"
      curl --fail --silent --show-error --max-time 5 "$url" >/dev/null || fail "$component readiness failed: $url"
      pass "$component ready: $url"
    done
    ;;
  *)
    printf 'Usage: %s {start|stop|reset|status} {all|prometheus|alertmanager|minio|thanos|runner}\n' "$0" >&2
    exit 2
    ;;
esac
