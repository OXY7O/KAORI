#!/usr/bin/env bash
set -Eeuo pipefail

domain=''
expected_ip=''
local_ready_url='http://127.0.0.1:5000/health/ready'

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
  bash deploy/nginx/verify-ingress.sh --domain DOMAIN [--expected-ip IPV4]

Required:
  --domain DOMAIN          Public KAORI hostname.

Options:
  --expected-ip IPV4       Require DNS to include this reviewed VPS IPv4.
  -h, --help               Show this help.
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$domain" ]] || fail '--domain is required'
[[ "$domain" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]] || \
  fail 'domain contains unsupported characters or labels'
if [[ -n "$expected_ip" ]]; then
  [[ "$expected_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail '--expected-ip must be an IPv4 address'
fi

for command_name in curl openssl getent grep awk sort ss; do
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"
done

verify_dns() {
  local -a resolved_ips=()
  local resolved_joined

  mapfile -t resolved_ips < <(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)
  ((${#resolved_ips[@]} > 0)) || fail "$domain has no IPv4 DNS resolution"
  resolved_joined="${resolved_ips[*]}"

  if [[ -n "$expected_ip" ]]; then
    printf '%s\n' "${resolved_ips[@]}" | grep -Fxq "$expected_ip" || \
      fail "$domain does not resolve to expected VPS IPv4 $expected_ip (resolved: $resolved_joined)"
  fi

  status '🌐' "DNS PASS · $domain → $resolved_joined"
}

verify_http_redirect() {
  local headers status_code location
  headers="$(curl --silent --show-error --max-time 10 --dump-header - --output /dev/null "http://$domain/health/ready")" || \
    fail "HTTP request to $domain failed"
  status_code="$(printf '%s\n' "$headers" | awk 'toupper($1) ~ /^HTTP\// {code=$2} END {print code}')"
  location="$(printf '%s\n' "$headers" | awk 'BEGIN {IGNORECASE=1} /^Location:/ {sub(/^[^:]+:[[:space:]]*/, ""); sub(/\r$/, ""); print; exit}')"

  [[ "$status_code" == '301' || "$status_code" == '308' ]] || \
    fail "HTTP did not redirect to HTTPS (status=${status_code:-missing})"
  [[ "$location" == "https://$domain/health/ready" ]] || \
    fail "HTTP redirect target is unexpected: ${location:-missing}"

  status '➡️' "HTTP redirect PASS · http://$domain → https://$domain"
}

capture_leaf_certificate() {
  openssl s_client -connect "$domain:443" -servername "$domain" -showcerts </dev/null 2>/dev/null |
    awk '/-----BEGIN CERTIFICATE-----/ {capture=1} capture {print} /-----END CERTIFICATE-----/ {exit}'
}

verify_tls() {
  local certificate san headers
  certificate="$(capture_leaf_certificate)"
  [[ "$certificate" == *'-----BEGIN CERTIFICATE-----'* ]] || fail 'unable to read the public TLS leaf certificate'

  printf '%s\n' "$certificate" | openssl x509 -noout -checkend 604800 >/dev/null || \
    fail 'TLS certificate expires within seven days'
  san="$(printf '%s\n' "$certificate" | openssl x509 -noout -ext subjectAltName)"
  printf '%s\n' "$san" | grep -Fq "DNS:$domain" || fail "TLS certificate SAN does not contain DNS:$domain"

  headers="$(curl --fail --silent --show-error --head --max-time 10 "https://$domain/health/ready")" || \
    fail 'trusted HTTPS request failed'
  printf '%s\n' "$headers" | grep -qi '^Strict-Transport-Security:' || fail 'HTTPS response is missing Strict-Transport-Security'

  status '🔒' "TLS PASS · trusted certificate for $domain"
}

verify_public_readiness() {
  curl --fail --silent --show-error --max-time 10 "https://$domain/health/ready" >/dev/null || \
    fail 'public HTTPS readiness failed'
  status '🩺' "HTTPS readiness PASS · https://$domain/health/ready"
}

verify_private_runtime_boundary() {
  local endpoint port
  local -a listeners=()

  curl --fail --silent --show-error --max-time 10 "$local_ready_url" >/dev/null || \
    fail "loopback readiness failed: $local_ready_url"

  mapfile -t listeners < <(ss -lntH | awk '{print $4}')
  for endpoint in "${listeners[@]}"; do
    if [[ "$endpoint" == *':5000' && "$endpoint" != '127.0.0.1:5000' && "$endpoint" != '[::1]:5000' ]]; then
      fail "KAORI port 5000 is bound beyond loopback: $endpoint"
    fi
    for port in 5432 6379; do
      if [[ "$endpoint" == *":$port" ]]; then
        fail "state-service port $port is unexpectedly listening on the host: $endpoint"
      fi
    done
  done

  status '✅' 'Private runtime PASS · KAORI loopback-only; PostgreSQL/Redis have no host listeners'
}

verify_unknown_host_rejection() {
  local invalid_http_code invalid_http_rc invalid_tls_output invalid_tls_rc

  set +e
  invalid_http_code="$(curl --silent --show-error --max-time 5 --output /dev/null --write-out '%{http_code}' \
    --header 'Host: invalid.kaori.invalid' http://127.0.0.1/)"
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

verify_dns
verify_http_redirect
verify_tls
verify_public_readiness
verify_private_runtime_boundary
verify_unknown_host_rejection

printf '\n✅ KAORI ingress verification PASS\n'
printf '🌐 Domain   %s\n' "$domain"
printf '🔒 HTTPS    https://%s\n' "$domain"
printf '🩺 Internal %s\n' "$local_ready_url"
