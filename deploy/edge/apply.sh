#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDGE_ROOT="${EDGE_ROOT:-/opt/shared-edge}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-$EDGE_ROOT/config/edge.env}"
EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"
EDGE_STATE_DIR="${EDGE_STATE_DIR:-$EDGE_ROOT/state}"
cutover_marker="$EDGE_STATE_DIR/cutover-complete"

fail() {
  printf '❌ Shared-edge apply failed · %s\n' "$*" >&2
  exit 1
}

status() {
  local icon="$1"
  shift
  printf '%s %s\n' "$icon" "$*"
}

bash "$SCRIPT_DIR/prepare.sh"

[[ -r "$EDGE_ENV_FILE" ]] || fail "shared-edge environment is not readable: $EDGE_ENV_FILE"
set -a
# shellcheck source=/dev/null
source "$EDGE_ENV_FILE"
set +a
EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"
mkdir -p "$EDGE_STATE_DIR"

compose=(
  docker compose
  --env-file "$EDGE_ENV_FILE"
  --project-directory "$SCRIPT_DIR"
  -f "$SCRIPT_DIR/compose.edge.yml"
)

status '🐳' 'Pulling immutable shared-edge images'
"${compose[@]}" pull nginx certbot >/dev/null

# First cutover must prove the KAORI frontend is already reachable on the shared network
# before the legacy public edge is stopped.
if [[ -f "$EDGE_SITES_DIR/kaori.env" ]]; then
  kaori_web="$(docker ps -q     --filter label=com.docker.compose.project=kaori-production     --filter label=com.docker.compose.service=web | head -n1)"
  [[ -n "$kaori_web" ]] || fail 'KAORI web container is missing before shared-edge cutover'
  kaori_networks="$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$kaori_web")"
  [[ "$kaori_networks" == *'"edge-public"'* ]] || fail 'KAORI web is not attached to edge-public'
  kaori_aliases="$(docker inspect --format '{{json (index .NetworkSettings.Networks "edge-public").Aliases}}' "$kaori_web")"
  [[ "$kaori_aliases" == *'"kaori-web"'* ]] || fail 'KAORI web is missing edge-public alias kaori-web'
  status '✅' 'KAORI shared-edge upstream attachment PASS'
fi

legacy_nginx=''
legacy_certbot=''
first_cutover=false
if [[ ! -f "$cutover_marker" ]]; then
  first_cutover=true
  legacy_nginx="$(docker ps -aq     --filter label=com.docker.compose.project=kaori-production     --filter label=com.docker.compose.service=nginx)"
  legacy_certbot="$(docker ps -aq     --filter label=com.docker.compose.project=kaori-production     --filter label=com.docker.compose.service=certbot)"
fi

rollback() {
  local reason="$1"
  printf '❌ Shared-edge cutover failed · %s\n' "$reason" >&2
  set +e
  "${compose[@]}" down >/dev/null 2>&1
  if [[ "$first_cutover" == 'true' ]]; then
    if [[ -n "$legacy_certbot" ]]; then
      # shellcheck disable=SC2086
      docker start $legacy_certbot >/dev/null 2>&1
    fi
    if [[ -n "$legacy_nginx" ]]; then
      # shellcheck disable=SC2086
      docker start $legacy_nginx >/dev/null 2>&1
    fi
    printf '↩️ Legacy KAORI edge rollback attempted\n' >&2
  fi
  set -e
  exit 1
}

if [[ "$first_cutover" == 'true' ]]; then
  status '🌐' 'Beginning one-time shared-edge cutover'
  if [[ -n "$legacy_certbot" ]]; then
    # shellcheck disable=SC2086
    docker stop $legacy_certbot >/dev/null || rollback 'unable to stop legacy Certbot'
  fi
  if [[ -n "$legacy_nginx" ]]; then
    # shellcheck disable=SC2086
    docker stop $legacy_nginx >/dev/null || rollback 'unable to stop legacy Nginx'
  fi
  status '✅' 'Legacy KAORI edge stopped; application runtime remains running'
fi

if ! "${compose[@]}" up -d --pull never nginx certbot; then
  rollback 'shared-edge containers did not start'
fi

if ! bash "$SCRIPT_DIR/verify.sh" --wait-seconds 360 --renewal-dry-run; then
  rollback 'shared-edge verification did not pass'
fi

date -u +%Y-%m-%dT%H:%M:%SZ > "$cutover_marker"
chmod 0600 "$cutover_marker"
status '✅' 'Shared-edge apply PASS'
status 'ℹ️' 'Legacy KAORI edge containers remain stopped after first cutover for deterministic emergency rollback'
