#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BASE_COMPOSE="${KAORI_BASE_COMPOSE:-$ROOT_DIR/compose.production.yml}"
VPS_COMPOSE="${KAORI_VPS_COMPOSE:-$ROOT_DIR/deploy/vps/compose.vps.yml}"
KAORI_DEPLOY_ENV_FILE="${KAORI_DEPLOY_ENV_FILE:-/etc/kaori/deploy.env}"
domain=''
expected_ip=''
renewal_dry_run=false

fail() {
  printf '❌ KAORI ingress verification failed · %s\n' "$*" >&2
  exit 1
}

status() {
  local icon="$1"
  shift
  printf '%s %s\n' "$icon" "$*"
}

usage() {
  cat <<'USAGE'
Usage:
  bash deploy/nginx/verify-ingress.sh --domain DOMAIN [--expected-ip IPV4] [--renewal-dry-run]
USAGE
}

while (($#)); do
  case "$1" in
    --domain)
      (($# >= 2)) || fail '--domain requires a value'
      domain="${2,,}"
      shift 2
      ;;
    --expected-ip)
      (($# >= 2)) || fail '--expected-ip requires a value'
      expected_ip="$2"
      shift 2
      ;;
    --renewal-dry-run)
      renewal_dry_run=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ -n "$domain" ]] || fail '--domain is required'
[[ "$domain" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]] || fail 'domain is invalid'
if [[ -n "$expected_ip" ]]; then
  [[ "$expected_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail '--expected-ip must be an IPv4 address'
fi

for command_name in curl openssl getent grep awk sort ss docker; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"
done
[[ -r "$KAORI_DEPLOY_ENV_FILE" ]] || fail "deployment environment is not readable: $KAORI_DEPLOY_ENV_FILE"
set -a
# shellcheck source=/dev/null
source "$KAORI_DEPLOY_ENV_FILE"
set +a
KAORI_APP_ENV_FILE="${KAORI_APP_ENV_FILE:-/etc/kaori/app.env}"
KAORI_SECRETS_ENV_FILE="${KAORI_SECRETS_ENV_FILE:-/etc/kaori/secrets.env}"
KAORI_RELEASE_ENV_FILE="${KAORI_RELEASE_ENV_FILE:-${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}}"
export KAORI_APP_ENV_FILE KAORI_SECRETS_ENV_FILE KAORI_RELEASE_ENV_FILE
# shellcheck source=deploy/vps/release-state.sh
source "$ROOT_DIR/deploy/vps/release-state.sh"
load_current_release_identity || fail 'release identity is unavailable for Compose verification'
compose=(docker compose --env-file "$KAORI_DEPLOY_ENV_FILE" -f "$BASE_COMPOSE" -f "$VPS_COMPOSE")

verify_dns() {
  local -a resolved_ips=()
  local resolved_joined
  mapfile -t resolved_ips < <(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)
  ((${#resolved_ips[@]} > 0)) || fail "$domain has no IPv4 DNS resolution"
  resolved_joined="${resolved_ips[*]}"
  if [[ -n "$expected_ip" ]]; then
    printf '%s\n' "${resolved_ips[@]}" | grep -Fxq "$expected_ip" || fail "$domain does not resolve to expected VPS IPv4 $expected_ip (resolved: $resolved_joined)"
  fi
  status '🌐' "DNS PASS · $domain → $resolved_joined"
}

verify_http_redirect() {
  local headers status_code location
  headers="$(curl --silent --show-error --max-time 10 --dump-header - --output /dev/null "http://$domain/health/ready")" || fail "HTTP request to $domain failed"
  status_code="$(printf '%s\n' "$headers" | awk 'toupper($1) ~ /^HTTP\// {code=$2} END {print code}')"
  location="$(printf '%s\n' "$headers" | awk 'BEGIN {IGNORECASE=1} /^Location:/ {sub(/^[^:]+:[[:space:]]*/, ""); sub(/\r$/, ""); print; exit}')"
  [[ "$status_code" == '301' || "$status_code" == '308' ]] || fail "HTTP did not redirect to HTTPS (status=${status_code:-missing})"
  [[ "$location" == "https://$domain/health/ready" ]] || fail "HTTP redirect target is unexpected: ${location:-missing}"
  status '➡️' "HTTP redirect PASS · http://$domain → https://$domain"
}

capture_leaf_certificate() {
  openssl s_client -connect "$domain:443" -servername "$domain" -showcerts </dev/null 2>/dev/null |
    awk '/-----BEGIN CERTIFICATE-----/ {capture=1} capture {print} /-----END CERTIFICATE-----/ {exit}'
}

verify_tls() {
  local certificate san headers
  certificate="$(capture_leaf_certificate)"
  [[ "$certificate" == *'-----BEGIN CERTIFICATE-----'* ]] || fail 'unable to read public TLS leaf certificate'
  printf '%s\n' "$certificate" | openssl x509 -noout -checkend 604800 >/dev/null || fail 'TLS certificate expires within seven days'
  san="$(printf '%s\n' "$certificate" | openssl x509 -noout -ext subjectAltName)"
  printf '%s\n' "$san" | grep -Fq "DNS:$domain" || fail "TLS certificate SAN does not contain DNS:$domain"
  headers="$(curl --fail --silent --show-error --head --max-time 10 "https://$domain/health/ready")" || fail 'trusted HTTPS request failed'
  printf '%s\n' "$headers" | grep -qi '^Strict-Transport-Security:' || fail 'HTTPS response is missing Strict-Transport-Security'
  status '🔒' "TLS PASS · trusted certificate for $domain"
}

verify_public_readiness() {
  curl --fail --silent --show-error --max-time 10 "https://$domain/health/ready" >/dev/null || fail 'public HTTPS readiness failed'
  status '🩺' "HTTPS readiness PASS · https://$domain/health/ready"
}

verify_internal_runtime() {
  "${compose[@]}" exec -T web python -c \
    "import urllib.request; request = urllib.request.Request('http://127.0.0.1:5000/health/ready', headers={'Host': 'localhost'}); urllib.request.urlopen(request, timeout=10).read()" \
    >/dev/null || fail 'internal web readiness failed inside the web container'

  local endpoint port
  local -a listeners=()
  mapfile -t listeners < <(ss -lntH | awk '{print $4}')
  for endpoint in "${listeners[@]}"; do
    for port in 5000 5432 6379; do
      if [[ "$endpoint" == *":$port" ]]; then
        fail "private runtime port $port is unexpectedly listening on the host: $endpoint"
      fi
    done
  done
  status '✅' 'Private runtime PASS · web/PostgreSQL/Redis have no host listeners'
}

verify_edge_containers() {
  local service cid configured_image expected_var expected_image
  for service in nginx certbot; do
    cid="$("${compose[@]}" ps -q "$service")"
    [[ -n "$cid" ]] || fail "$service has no container"
    [[ "$(docker inspect --format '{{.State.Status}}' "$cid")" == 'running' ]] || fail "$service is not running"
    if [[ "$service" == 'nginx' ]]; then
      expected_var='KAORI_NGINX_IMAGE'
    else
      expected_var='KAORI_CERTBOT_IMAGE'
    fi
    expected_image="${!expected_var:-}"
    [[ "$expected_image" =~ @sha256:[0-9a-f]{64}$ ]] || fail "$expected_var is not immutable"
    configured_image="$(docker inspect --format '{{.Config.Image}}' "$cid")"
    [[ "$configured_image" == "$expected_image" ]] || fail "$service is not running the reviewed immutable image"
  done
  status '🐳' 'Immutable Nginx / Certbot images PASS'
}

verify_unknown_host_rejection() {
  local invalid_http_code invalid_http_rc invalid_tls_output invalid_tls_rc
  set +e
  invalid_http_code="$(curl --silent --show-error --max-time 5 --output /dev/null --write-out '%{http_code}' --header 'Host: invalid.kaori.invalid' http://127.0.0.1/)"
  invalid_http_rc=$?
  set -e
  if [[ "$invalid_http_code" != '000' || "$invalid_http_rc" -eq 0 ]]; then
    fail "unknown HTTP Host was not rejected (status=$invalid_http_code rc=$invalid_http_rc)"
  fi

  set +e
  invalid_tls_output="$(openssl s_client -connect 127.0.0.1:443 -servername invalid.kaori.invalid </dev/null 2>&1)"
  invalid_tls_rc=$?
  set -e
  [[ "$invalid_tls_output" != *'-----BEGIN CERTIFICATE-----'* ]] || fail 'unknown TLS SNI received a certificate'
  [[ "$invalid_tls_rc" -ne 0 ]] || fail 'unknown TLS SNI handshake unexpectedly succeeded'
  status '🔐' 'Unknown Host/SNI rejection PASS'
}

verify_renewal() {
  [[ "$renewal_dry_run" == 'true' ]] || return 0
  status '🔒' 'Running Certbot renewal dry-run'
  "${compose[@]}" exec -T certbot certbot renew --dry-run --webroot --webroot-path /var/www/certbot
  status '✅' 'Certbot renewal dry-run PASS'
}

verify_dns
verify_http_redirect
verify_tls
verify_public_readiness
verify_internal_runtime
verify_edge_containers
verify_unknown_host_rejection
verify_renewal

printf '\n✅ KAORI ingress verification PASS\n'
printf '🌐 Domain   %s\n' "$domain"
printf '🔒 HTTPS    https://%s\n' "$domain"
