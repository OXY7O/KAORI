#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDGE_ROOT="${EDGE_ROOT:-/opt/shared-edge}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-$EDGE_ROOT/config/edge.env}"
EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"
renewal_dry_run=false
wait_seconds=360

fail() {
  printf '❌ Shared-edge verification failed · %s\n' "$*" >&2
  exit 1
}

status() {
  local icon="$1"
  shift
  printf '%s %s\n' "$icon" "$*"
}

while (($#)); do
  case "$1" in
    --renewal-dry-run) renewal_dry_run=true; shift ;;
    --wait-seconds)
      (($# >= 2)) || fail '--wait-seconds requires a value'
      wait_seconds="$2"
      shift 2
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ "$wait_seconds" =~ ^[0-9]+$ ]] || fail '--wait-seconds must be numeric'
for command_name in curl openssl getent grep awk sort ss docker; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"
done
[[ -r "$EDGE_ENV_FILE" ]] || fail "shared-edge environment is not readable: $EDGE_ENV_FILE"
set -a
# shellcheck source=/dev/null
source "$EDGE_ENV_FILE"
set +a
EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"
export EDGE_SITES_DIR
[[ -d "$EDGE_SITES_DIR" ]] || fail "shared-edge sites directory is missing: $EDGE_SITES_DIR"
[[ "${EDGE_PUBLIC_IP:-}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail 'EDGE_PUBLIC_IP must be an IPv4 address'

compose=(
  docker compose
  --env-file "$EDGE_ENV_FILE"
  --project-directory "$SCRIPT_DIR"
  -f "$SCRIPT_DIR/compose.yml"
)

verify_edge_containers() {
  local service cid configured_image expected_image
  for service in nginx certbot; do
    cid="$("${compose[@]}" ps -q "$service")"
    [[ -n "$cid" ]] || fail "$service has no shared-edge container"
    [[ "$(docker inspect --format '{{.State.Status}}' "$cid")" == 'running' ]] || fail "$service is not running"
    if [[ "$service" == 'nginx' ]]; then
      expected_image="${EDGE_NGINX_IMAGE:-}"
    else
      expected_image="${EDGE_CERTBOT_IMAGE:-}"
    fi
    [[ "$expected_image" =~ @sha256:[0-9a-f]{64}$ ]] || fail "$service expected image is not immutable"
    configured_image="$(docker inspect --format '{{.Config.Image}}' "$cid")"
    [[ "$configured_image" == "$expected_image" ]] || fail "$service is not running the reviewed immutable image"
  done
  status '🐳' 'Immutable shared-edge Nginx / Certbot images PASS'
}

load_site() {
  local site_file="$1"
  EDGE_DOMAIN=''
  EDGE_TLS='true'
  EDGE_HEALTH_PATH='/'
  # shellcheck source=/dev/null
  source "$site_file"
  [[ "$EDGE_DOMAIN" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]] || fail "invalid EDGE_DOMAIN in $site_file"
  [[ "$EDGE_HEALTH_PATH" == /* ]] || fail "EDGE_HEALTH_PATH must start with / in $site_file"
  [[ "$EDGE_TLS" == 'true' || "$EDGE_TLS" == 'false' ]] || fail "EDGE_TLS must be true or false in $site_file"
}

verify_dns() {
  local domain="$1"
  local -a resolved_ips=()
  local resolved_joined
  mapfile -t resolved_ips < <(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)
  ((${#resolved_ips[@]} > 0)) || fail "$domain has no IPv4 DNS resolution"
  resolved_joined="${resolved_ips[*]}"
  printf '%s\n' "${resolved_ips[@]}" | grep -Fxq "$EDGE_PUBLIC_IP" ||     fail "$domain does not resolve to expected edge IPv4 $EDGE_PUBLIC_IP (resolved: $resolved_joined)"
  status '🌐' "DNS PASS · $domain → $resolved_joined"
}

verify_http_redirect() {
  local domain="$1" health_path="$2"
  local headers status_code location
  headers="$(curl --silent --show-error --max-time 10 --dump-header - --output /dev/null "http://$domain$health_path")" ||     fail "HTTP request to $domain failed"
  status_code="$(printf '%s\n' "$headers" | awk 'toupper($1) ~ /^HTTP\// {code=$2} END {print code}')"
  location="$(printf '%s\n' "$headers" | awk 'BEGIN {IGNORECASE=1} /^Location:/ {sub(/^[^:]+:[[:space:]]*/, ""); sub(/\r$/, ""); print; exit}')"
  [[ "$status_code" == '301' || "$status_code" == '308' ]] || fail "$domain HTTP did not redirect to HTTPS (status=${status_code:-missing})"
  [[ "$location" == "https://$domain$health_path" ]] || fail "$domain HTTP redirect target is unexpected: ${location:-missing}"
  status '➡️' "HTTP redirect PASS · http://$domain → https://$domain"
}

capture_leaf_certificate() {
  local domain="$1"
  openssl s_client -connect "$domain:443" -servername "$domain" -showcerts </dev/null 2>/dev/null |
    awk '/-----BEGIN CERTIFICATE-----/ {capture=1} capture {print} /-----END CERTIFICATE-----/ {exit}'
}

verify_tls_site() {
  local domain="$1" health_path="$2"
  local deadline certificate san headers
  deadline=$(( $(date +%s) + wait_seconds ))
  while (( $(date +%s) < deadline )); do
    if curl --fail --silent --show-error --max-time 10 "https://$domain$health_path" >/dev/null 2>&1; then
      break
    fi
    sleep 5
  done
  curl --fail --silent --show-error --max-time 10 "https://$domain$health_path" >/dev/null ||     fail "HTTPS readiness did not become healthy for $domain before timeout"

  certificate="$(capture_leaf_certificate "$domain")"
  [[ "$certificate" == *'-----BEGIN CERTIFICATE-----'* ]] || fail "unable to read public TLS leaf certificate for $domain"
  printf '%s\n' "$certificate" | openssl x509 -noout -checkend 604800 >/dev/null || fail "$domain TLS certificate expires within seven days"
  san="$(printf '%s\n' "$certificate" | openssl x509 -noout -ext subjectAltName)"
  printf '%s\n' "$san" | grep -Fq "DNS:$domain" || fail "$domain TLS certificate SAN does not contain DNS:$domain"

  headers="$(curl --fail --silent --show-error --max-time 10 --dump-header - --output /dev/null "https://$domain$health_path")" ||     fail "trusted HTTPS request failed for $domain"
  printf '%s\n' "$headers" | grep -qi '^Strict-Transport-Security:' || fail "$domain HTTPS response is missing Strict-Transport-Security"
  status '🔒' "TLS PASS · trusted certificate for $domain"
  status '🩺' "HTTPS readiness PASS · https://$domain$health_path"
}

verify_http_site() {
  local domain="$1" health_path="$2"
  curl --fail --silent --show-error --max-time 10 "http://$domain$health_path" >/dev/null ||     fail "HTTP readiness failed for non-TLS site $domain"
  status '🩺' "HTTP readiness PASS · http://$domain$health_path"
}

site_count=0
for site_file in "$EDGE_SITES_DIR"/*.env; do
  [[ -f "$site_file" ]] || continue
  load_site "$site_file"
  site_count=$((site_count + 1))
  verify_dns "$EDGE_DOMAIN"
  if [[ "$EDGE_TLS" == 'true' ]]; then
    verify_http_redirect "$EDGE_DOMAIN" "$EDGE_HEALTH_PATH"
    verify_tls_site "$EDGE_DOMAIN" "$EDGE_HEALTH_PATH"
  else
    verify_http_site "$EDGE_DOMAIN" "$EDGE_HEALTH_PATH"
  fi
done
(( site_count > 0 )) || fail "no active site registrations found in $EDGE_SITES_DIR"

verify_edge_containers

invalid_http_code=''
invalid_http_rc=0
set +e
invalid_http_code="$(curl --silent --show-error --max-time 5 --output /dev/null --write-out '%{http_code}' --header 'Host: invalid.shared-edge.invalid' http://127.0.0.1/)"
invalid_http_rc=$?
set -e
if [[ "$invalid_http_code" != '000' || "$invalid_http_rc" -eq 0 ]]; then
  fail "unknown HTTP Host was not rejected (status=$invalid_http_code rc=$invalid_http_rc)"
fi

invalid_tls_output=''
invalid_tls_rc=0
set +e
invalid_tls_output="$(openssl s_client -connect 127.0.0.1:443 -servername invalid.shared-edge.invalid </dev/null 2>&1)"
invalid_tls_rc=$?
set -e
[[ "$invalid_tls_output" != *'-----BEGIN CERTIFICATE-----'* ]] || fail 'unknown TLS SNI received a certificate'
[[ "$invalid_tls_rc" -ne 0 ]] || fail 'unknown TLS SNI handshake unexpectedly succeeded'
status '🔐' 'Unknown Host/SNI rejection PASS'

if [[ "$renewal_dry_run" == 'true' ]]; then
  status '🔒' 'Running Certbot renewal dry-run for registered TLS lineages'
  "${compose[@]}" exec -T certbot certbot renew --dry-run --webroot --webroot-path /var/www/certbot
  status '✅' 'Certbot renewal dry-run PASS'
fi

printf '\n✅ Shared-edge verification PASS\n'
