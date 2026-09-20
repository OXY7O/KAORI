#!/usr/bin/env bash
set -Eeuo pipefail

EDGE_ROOT="${EDGE_ROOT:-/opt/shared-edge}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-$EDGE_ROOT/config/edge.env}"
site_id=''
domain=''
container=''
alias_name=''
upstream_port=''
health_path='/'
tls='true'
websocket='false'
client_max_body_size='25m'

fail() {
  printf '❌ Edge publication registration failed · %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  publish-container.sh \
    --site-id ID \
    --domain DOMAIN \
    --container CONTAINER \
    --alias ALIAS \
    --port PORT \
    [--health-path PATH] \
    [--tls true|false] \
    [--websocket true|false] \
    [--client-max-body-size SIZE]
USAGE
}

while (($#)); do
  case "$1" in
    --site-id) site_id="${2:?}"; shift 2 ;;
    --domain) domain="${2:?}"; shift 2 ;;
    --container) container="${2:?}"; shift 2 ;;
    --alias) alias_name="${2:?}"; shift 2 ;;
    --port) upstream_port="${2:?}"; shift 2 ;;
    --health-path) health_path="${2:?}"; shift 2 ;;
    --tls) tls="${2:?}"; shift 2 ;;
    --websocket) websocket="${2:?}"; shift 2 ;;
    --client-max-body-size) client_max_body_size="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ "$site_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail '--site-id is required and must be filesystem-safe'
[[ "$domain" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]] || fail '--domain is invalid'
[[ "$alias_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail '--alias is invalid'
[[ "$upstream_port" =~ ^[0-9]+$ ]] && (( upstream_port >= 1 && upstream_port <= 65535 )) || fail '--port is invalid'
[[ "$health_path" == /* ]] || fail '--health-path must start with /'
[[ "$tls" == 'true' || "$tls" == 'false' ]] || fail '--tls must be true or false'
[[ "$websocket" == 'true' || "$websocket" == 'false' ]] || fail '--websocket must be true or false'
[[ "$client_max_body_size" =~ ^[0-9]+[kKmMgG]?$ ]] || fail '--client-max-body-size is invalid'
[[ -n "$container" ]] || fail '--container is required'
[[ -r "$EDGE_ENV_FILE" ]] || fail "standalone edge environment is not readable: $EDGE_ENV_FILE"

set -a
# shellcheck source=/dev/null
source "$EDGE_ENV_FILE"
set +a
EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"
mkdir -p "$EDGE_SITES_DIR"

docker network inspect edge-public >/dev/null 2>&1 || fail 'edge-public is missing; run prepare.sh first'
docker inspect "$container" >/dev/null 2>&1 || fail "container does not exist: $container"
[[ "$(docker inspect --format '{{.State.Status}}' "$container")" == 'running' ]] || fail "container is not running: $container"

networks="$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$container")"
if [[ "$networks" == *'"edge-public"'* ]]; then
  aliases="$(docker inspect --format '{{json (index .NetworkSettings.Networks "edge-public").Aliases}}' "$container")"
  [[ "$aliases" == *"\"$alias_name\""* ]] ||     fail "container is already on edge-public without required alias $alias_name; disconnect/reconnect explicitly before publishing"
else
  docker network connect --alias "$alias_name" edge-public "$container"
fi

temporary="$(mktemp "$EDGE_SITES_DIR/.${site_id}.env.XXXXXX")"
cat > "$temporary" <<EOF
EDGE_DOMAIN=$domain
EDGE_UPSTREAM=$alias_name
EDGE_UPSTREAM_PORT=$upstream_port
EDGE_TLS=$tls
EDGE_HEALTH_PATH=$health_path
EDGE_WEBSOCKET=$websocket
EDGE_CLIENT_MAX_BODY_SIZE=$client_max_body_size
EOF
chmod 0640 "$temporary"
mv "$temporary" "$EDGE_SITES_DIR/$site_id.env"

printf '✅ Edge registration written · %s → %s:%s\n' "$domain" "$alias_name" "$upstream_port"
printf 'ℹ️ Application lifecycle was not restarted or modified beyond edge-public attachment\n'
