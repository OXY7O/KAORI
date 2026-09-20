#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDGE_ROOT="${EDGE_ROOT:-/opt/shared-edge}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-$EDGE_ROOT/config/edge.env}"

fail() {
  printf '❌ Standalone edge preparation failed · %s\n' "$*" >&2
  exit 1
}

status() {
  local icon="$1"
  shift
  printf '%s %s\n' "$icon" "$*"
}

for command_name in docker stat; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"
done

[[ "$EDGE_ROOT" =~ ^/[A-Za-z0-9._/-]+$ && "$EDGE_ROOT" != '/' ]] || fail 'EDGE_ROOT must be a safe absolute path'
[[ -f "$EDGE_ENV_FILE" && ! -L "$EDGE_ENV_FILE" && -r "$EDGE_ENV_FILE" ]] ||   fail "copy edge.env.example to the standalone edge configuration path first: $EDGE_ENV_FILE"
mode="$(stat -c '%a' "$EDGE_ENV_FILE")"
[[ "$mode" == '600' || "$mode" == '640' ]] || fail 'edge.env must use mode 600 or 640'

set -a
# shellcheck source=/dev/null
source "$EDGE_ENV_FILE"
set +a

EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"
EDGE_CERTIFICATE_DIR="${EDGE_CERTIFICATE_DIR:-$EDGE_ROOT/state/letsencrypt}"
EDGE_ACME_WEBROOT_DIR="${EDGE_ACME_WEBROOT_DIR:-$EDGE_ROOT/state/acme-webroot}"
export EDGE_SITES_DIR EDGE_CERTIFICATE_DIR EDGE_ACME_WEBROOT_DIR

for image_var in EDGE_NGINX_IMAGE EDGE_CERTBOT_IMAGE; do
  value="${!image_var:-}"
  [[ "$value" =~ @sha256:[0-9a-f]{64}$ ]] || fail "$image_var must be immutable and digest-qualified"
done
[[ "${EDGE_PUBLIC_IP:-}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail 'EDGE_PUBLIC_IP must be an IPv4 address'
[[ -n "${EDGE_LETSENCRYPT_EMAIL:-}" ]] || fail 'EDGE_LETSENCRYPT_EMAIL is required'

mkdir -p "$EDGE_SITES_DIR" "$EDGE_CERTIFICATE_DIR" "$EDGE_ACME_WEBROOT_DIR"

if docker network inspect edge-public >/dev/null 2>&1; then
  status '✅' 'Standalone edge network already exists · edge-public'
else
  docker network create edge-public >/dev/null
  status '✅' 'Created standalone edge network · edge-public'
fi

compose=(
  docker compose
  --env-file "$EDGE_ENV_FILE"
  --project-directory "$SCRIPT_DIR"
  -f "$SCRIPT_DIR/compose.yml"
)
"${compose[@]}" config --quiet || fail 'standalone edge Compose validation failed'

status '✅' 'Standalone edge prepare PASS · no application or public listener was changed'
