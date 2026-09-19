#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE=(docker compose --env-file "$SCRIPT_DIR/.env" -f "$SCRIPT_DIR/compose.yml")

fail() {
  printf 'KAORI laptop example: %s\n' "$*" >&2
  exit 1
}

[[ -f "$SCRIPT_DIR/.env" ]] || fail 'missing .env; copy .env.example to .env first'
command -v docker >/dev/null 2>&1 || fail 'docker is required'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is required'

set -a
# shellcheck source=/dev/null
source "$SCRIPT_DIR/.env"
set +a

validate_release() {
  : "${KAORI_IMAGE:?Set KAORI_IMAGE in .env}"
  : "${APP_BUILD_SHA:?Set APP_BUILD_SHA in .env}"
  [[ "$APP_BUILD_SHA" =~ ^[0-9a-f]{40}$ ]] || fail 'APP_BUILD_SHA must be the exact 40-character admitted staging SHA'
  [[ "$APP_BUILD_SHA" != '0000000000000000000000000000000000000000' ]] || fail 'replace the placeholder APP_BUILD_SHA with the admitted staging SHA'
  [[ "$KAORI_IMAGE" != *':staging' ]] || fail 'mutable :staging images are not supported; use an admitted RC tag or digest'
  [[ "$KAORI_IMAGE" =~ (-rc\.[0-9]+$|@sha256:[0-9a-f]{64}$) ]] || fail 'KAORI_IMAGE must be an admitted RC tag or digest-qualified image'
}

start() {
  validate_release
  "${COMPOSE[@]}" pull
  "${COMPOSE[@]}" up -d postgres redis
  "${COMPOSE[@]}" run --rm migrate
  "${COMPOSE[@]}" up -d web worker beat
  printf 'KAORI is starting at http://localhost:%s\n' "${KAORI_PORT:-5000}"
  status
}

status() {
  "${COMPOSE[@]}" ps
}

logs() {
  "${COMPOSE[@]}" logs --tail=200 -f web worker beat
}

stop() {
  "${COMPOSE[@]}" down
}

reset() {
  "${COMPOSE[@]}" down --volumes --remove-orphans
}

case "${1:-}" in
  start) start ;;
  status) status ;;
  logs) logs ;;
  stop) stop ;;
  reset) reset ;;
  *) fail 'usage: ./run.sh {start|status|logs|stop|reset}' ;;
esac
