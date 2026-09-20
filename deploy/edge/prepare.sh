#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDGE_ROOT="${EDGE_ROOT:-/opt/shared-edge}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-$EDGE_ROOT/config/edge.env}"
EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"
EDGE_CERTIFICATE_DIR="${EDGE_CERTIFICATE_DIR:-$EDGE_ROOT/state/letsencrypt}"
EDGE_ACME_WEBROOT_DIR="${EDGE_ACME_WEBROOT_DIR:-$EDGE_ROOT/state/acme-webroot}"
LEGACY_KAORI_DEPLOY_ENV_FILE="${LEGACY_KAORI_DEPLOY_ENV_FILE:-/etc/kaori/deploy.env}"

fail() {
  printf '❌ Shared-edge preparation failed · %s\n' "$*" >&2
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
mkdir -p "$EDGE_ROOT/config" "$EDGE_SITES_DIR" "$EDGE_CERTIFICATE_DIR" "$EDGE_ACME_WEBROOT_DIR"

bootstrap_edge_environment() {
  [[ -e "$EDGE_ENV_FILE" ]] && return 0
  [[ -r "$LEGACY_KAORI_DEPLOY_ENV_FILE" ]] || fail "legacy KAORI deploy environment is required for first migration: $LEGACY_KAORI_DEPLOY_ENV_FILE"

  set -a
  # shellcheck source=/dev/null
  source "$LEGACY_KAORI_DEPLOY_ENV_FILE"
  set +a

  local nginx_image certbot_image email public_ip
  nginx_image="${EDGE_NGINX_IMAGE_BOOTSTRAP:-${KAORI_NGINX_IMAGE:-}}"
  certbot_image="${EDGE_CERTBOT_IMAGE_BOOTSTRAP:-${KAORI_CERTBOT_IMAGE:-}}"
  email="${EDGE_LETSENCRYPT_EMAIL_BOOTSTRAP:-${KAORI_LETSENCRYPT_EMAIL:-}}"
  public_ip="${EDGE_PUBLIC_IP_BOOTSTRAP:-${KAORI_PUBLIC_IP:-}}"

  [[ "$nginx_image" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'legacy KAORI_NGINX_IMAGE is missing or not immutable'
  [[ "$certbot_image" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'legacy KAORI_CERTBOT_IMAGE is missing or not immutable'
  [[ -n "$email" ]] || fail 'Let\047s Encrypt email is required to bootstrap shared edge'
  [[ "$public_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail 'legacy KAORI_PUBLIC_IP is missing or invalid'

  cat > "$EDGE_ENV_FILE" <<EOF
EDGE_NGINX_IMAGE=$nginx_image
EDGE_CERTBOT_IMAGE=$certbot_image
EDGE_LETSENCRYPT_EMAIL=$email
EDGE_PUBLIC_IP=$public_ip
EDGE_SITES_DIR=$EDGE_SITES_DIR
EDGE_CERTIFICATE_DIR=$EDGE_CERTIFICATE_DIR
EDGE_ACME_WEBROOT_DIR=$EDGE_ACME_WEBROOT_DIR
EDGE_RELOAD_INTERVAL_SECONDS=30
EDGE_CERTBOT_RENEW_INTERVAL_SECONDS=43200
EOF
  chmod 0640 "$EDGE_ENV_FILE"
  status '✅' "Bootstrapped independent shared-edge environment · $EDGE_ENV_FILE"
}

bootstrap_edge_environment
[[ -f "$EDGE_ENV_FILE" && ! -L "$EDGE_ENV_FILE" && -r "$EDGE_ENV_FILE" ]] || fail "shared-edge environment must be a readable regular non-symlink file: $EDGE_ENV_FILE"
mode="$(stat -c '%a' "$EDGE_ENV_FILE")"
[[ "$mode" == '600' || "$mode" == '640' ]] || fail 'shared-edge environment must use mode 600 or 640'

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
  status '✅' 'Shared Docker network already exists · edge-public'
else
  docker network create edge-public >/dev/null
  status '✅' 'Created shared Docker network · edge-public'
fi

bootstrap_kaori_site() {
  local kaori_site="$EDGE_SITES_DIR/kaori.env"
  [[ -e "$kaori_site" ]] && return 0
  [[ -r "$LEGACY_KAORI_DEPLOY_ENV_FILE" ]] || fail 'legacy KAORI deploy environment is required to bootstrap KAORI site registration'

  set -a
  # shellcheck source=/dev/null
  source "$LEGACY_KAORI_DEPLOY_ENV_FILE"
  set +a
  : "${KAORI_PUBLIC_DOMAIN:?KAORI_PUBLIC_DOMAIN is required for initial edge migration}"

  cat > "$kaori_site" <<EOF
EDGE_DOMAIN=$KAORI_PUBLIC_DOMAIN
EDGE_UPSTREAM=kaori-web
EDGE_UPSTREAM_PORT=5000
EDGE_TLS=true
EDGE_HEALTH_PATH=/health/ready
EDGE_WEBSOCKET=false
EDGE_CLIENT_MAX_BODY_SIZE=25m
EOF
  chmod 0640 "$kaori_site"
  status '✅' "Bootstrapped KAORI site registration · $kaori_site"
}

bootstrap_kaori_site

# Preserve the currently trusted KAORI certificate lineage on the first cutover.
kaori_site="$EDGE_SITES_DIR/kaori.env"
# shellcheck source=/dev/null
source "$kaori_site"
kaori_domain="$EDGE_DOMAIN"
if [[ ! -s "$EDGE_CERTIFICATE_DIR/live/$kaori_domain/fullchain.pem" ]]; then
  if docker volume inspect kaori-vps-letsencrypt >/dev/null 2>&1; then
    status '🔐' 'Migrating legacy KAORI Let\047s Encrypt lineage into shared-edge state'
    docker run --rm       --entrypoint /bin/sh       --volume kaori-vps-letsencrypt:/legacy:ro       --volume "$EDGE_CERTIFICATE_DIR:/target"       "$EDGE_CERTBOT_IMAGE"       -ec 'cp -a /legacy/. /target/'
    [[ -s "$EDGE_CERTIFICATE_DIR/live/$kaori_domain/fullchain.pem" ]] || fail 'legacy certificate migration did not produce the KAORI fullchain'
    [[ -s "$EDGE_CERTIFICATE_DIR/live/$kaori_domain/privkey.pem" ]] || fail 'legacy certificate migration did not produce the KAORI private key'
    status '✅' "Legacy certificate lineage migrated · $kaori_domain"
  else
    status 'ℹ️' 'Legacy certificate volume not found; Certbot will issue registered TLS certificates during apply'
  fi
else
  status '✅' "Shared-edge certificate lineage already present · $kaori_domain"
fi

compose=(
  docker compose
  --env-file "$EDGE_ENV_FILE"
  --project-directory "$SCRIPT_DIR"
  -f "$SCRIPT_DIR/compose.edge.yml"
)
"${compose[@]}" config --quiet || fail 'shared-edge Compose configuration validation failed'

status '✅' 'Shared-edge prepare PASS · no public ports were mutated'
