#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDGE_ROOT="${EDGE_ROOT:-/opt/shared-edge}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-$EDGE_ROOT/config/edge.env}"
KAORI_DOMAIN="${KAORI_DOMAIN:-kaori.cloud}"

fail() {
  printf '❌ KAORI edge migration example failed · %s\n' "$*" >&2
  exit 1
}

bash "$SCRIPT_DIR/prepare.sh"

set -a
# shellcheck source=/dev/null
source "$EDGE_ENV_FILE"
set +a
EDGE_CERTIFICATE_DIR="${EDGE_CERTIFICATE_DIR:-$EDGE_ROOT/state/letsencrypt}"
mkdir -p "$EDGE_CERTIFICATE_DIR"

kaori_web="$(docker ps -q   --filter label=com.docker.compose.project=kaori-production   --filter label=com.docker.compose.service=web | head -n1)"
[[ -n "$kaori_web" ]] || fail 'running KAORI web container was not found'
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$kaori_web")" == 'healthy' ]] || fail 'KAORI web must be healthy before publication'

if [[ ! -s "$EDGE_CERTIFICATE_DIR/live/$KAORI_DOMAIN/fullchain.pem" ]] && docker volume inspect kaori-vps-letsencrypt >/dev/null 2>&1; then
  printf '🔐 Migrating existing KAORI certificate lineage into standalone edge state\n'
  docker run --rm     --entrypoint /bin/sh     --volume kaori-vps-letsencrypt:/legacy:ro     --volume "$EDGE_CERTIFICATE_DIR:/target"     "$EDGE_CERTBOT_IMAGE"     -ec 'cp -a /legacy/. /target/'
fi

bash "$SCRIPT_DIR/publish-container.sh"   --site-id kaori   --domain "$KAORI_DOMAIN"   --container "$kaori_web"   --alias kaori-web   --port 5000   --health-path /health/ready   --tls true   --websocket false   --client-max-body-size 25m

legacy_nginx="$(docker ps -q   --filter label=com.docker.compose.project=kaori-production   --filter label=com.docker.compose.service=nginx)"
legacy_certbot="$(docker ps -q   --filter label=com.docker.compose.project=kaori-production   --filter label=com.docker.compose.service=certbot)"

rollback() {
  printf '↩️ Standalone edge verification failed; restoring legacy KAORI edge\n' >&2
  docker compose --env-file "$EDGE_ENV_FILE" --project-directory "$SCRIPT_DIR" -f "$SCRIPT_DIR/compose.yml" down >/dev/null 2>&1 || true
  [[ -z "$legacy_certbot" ]] || docker start $legacy_certbot >/dev/null 2>&1 || true
  [[ -z "$legacy_nginx" ]] || docker start $legacy_nginx >/dev/null 2>&1 || true
  exit 1
}

[[ -z "$legacy_certbot" ]] || docker stop $legacy_certbot >/dev/null || fail 'unable to stop legacy KAORI Certbot'
[[ -z "$legacy_nginx" ]] || docker stop $legacy_nginx >/dev/null || fail 'unable to stop legacy KAORI Nginx'

bash "$SCRIPT_DIR/apply.sh" || rollback

printf '✅ KAORI publication example cutover PASS · https://%s\n' "$KAORI_DOMAIN"
printf 'ℹ️ KAORI application deployment remains independent from this public-edge lifecycle\n'
