#!/bin/sh
set -eu

sites_dir="${EDGE_SITES_DIR:-/etc/shared-edge/sites}"
email="${EDGE_LETSENCRYPT_EMAIL:?EDGE_LETSENCRYPT_EMAIL is required}"
renew_interval="${EDGE_CERTBOT_RENEW_INTERVAL_SECONDS:-43200}"
issue_retry_interval="${EDGE_CERTBOT_ISSUE_RETRY_SECONDS:-30}"
webroot=/var/www/certbot

case "$renew_interval" in
  ''|*[!0-9]*) printf '❌ invalid EDGE_CERTBOT_RENEW_INTERVAL_SECONDS\n' >&2; exit 1 ;;
esac
[ "$renew_interval" -ge 3600 ] || {
  printf '❌ EDGE_CERTBOT_RENEW_INTERVAL_SECONDS must be at least 3600\n' >&2
  exit 1
}
case "$issue_retry_interval" in
  ''|*[!0-9]*) printf '❌ invalid EDGE_CERTBOT_ISSUE_RETRY_SECONDS\n' >&2; exit 1 ;;
esac
[ "$issue_retry_interval" -ge 10 ] || {
  printf '❌ EDGE_CERTBOT_ISSUE_RETRY_SECONDS must be at least 10\n' >&2
  exit 1
}
[ -d "$sites_dir" ] || {
  printf '❌ shared-edge site directory is missing: %s\n' "$sites_dir" >&2
  exit 1
}

load_site() {
  site_file="$1"
  EDGE_DOMAIN=''
  EDGE_TLS='true'
  # shellcheck source=/dev/null
  . "$site_file"
  printf '%s\n' "$EDGE_DOMAIN" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$' || {
    printf '❌ invalid EDGE_DOMAIN in %s\n' "$site_file" >&2
    return 1
  }
  case "$EDGE_TLS" in true|false) ;; *) printf '❌ EDGE_TLS must be true or false in %s\n' "$site_file" >&2; return 1 ;; esac
}

certificate_ready() {
  domain="$1"
  [ -s "/etc/letsencrypt/live/$domain/fullchain.pem" ] &&
    [ -s "/etc/letsencrypt/live/$domain/privkey.pem" ]
}

issue_site() {
  domain="$1"
  printf '🔒 Requesting Let\047s Encrypt certificate · %s\n' "$domain"
  certbot certonly     --non-interactive     --agree-tos     --email "$email"     --webroot     --webroot-path "$webroot"     --cert-name "$domain"     --domain "$domain"     --keep-until-expiring
  certificate_ready "$domain" || {
    printf '❌ certificate files were not created for %s\n' "$domain" >&2
    return 1
  }
  printf '✅ Certificate available · %s\n' "$domain"
}

ensure_site_certificates() {
  found_tls=false
  incomplete=false
  for site_file in "$sites_dir"/*.env; do
    [ -f "$site_file" ] || continue
    load_site "$site_file"
    [ "$EDGE_TLS" = 'true' ] || continue
    found_tls=true
    if ! certificate_ready "$EDGE_DOMAIN"; then
      if ! issue_site "$EDGE_DOMAIN"; then
        incomplete=true
      fi
    fi
    certificate_ready "$EDGE_DOMAIN" || incomplete=true
  done
  [ "$found_tls" = 'true' ] || printf 'ℹ️ No TLS-enabled shared-edge registrations require Certbot\n'
  [ "$incomplete" = 'false' ]
}

renew_certificates() {
  printf '🔒 Checking shared-edge certificate renewal\n'
  certbot renew     --non-interactive     --webroot     --webroot-path "$webroot"     --quiet || true
  printf '✅ Shared-edge certificate renewal check complete\n'
}

while :; do
  if ensure_site_certificates; then
    renew_certificates
    sleep "$renew_interval" &
  else
    printf '⚠️ Shared-edge certificate issuance remains incomplete; retrying in %ss\n' "$issue_retry_interval" >&2
    sleep "$issue_retry_interval" &
  fi
  wait $! || true
done
