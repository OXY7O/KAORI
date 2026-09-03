#!/bin/sh
set -eu

domain="${KAORI_PUBLIC_DOMAIN:?KAORI_PUBLIC_DOMAIN is required}"
email="${KAORI_LETSENCRYPT_EMAIL:?KAORI_LETSENCRYPT_EMAIL is required}"
renew_interval="${KAORI_CERTBOT_RENEW_INTERVAL_SECONDS:-43200}"
webroot=/var/www/certbot
fullchain="/etc/letsencrypt/live/$domain/fullchain.pem"
privkey="/etc/letsencrypt/live/$domain/privkey.pem"

case "$renew_interval" in
  ''|*[!0-9]*) printf '❌ invalid KAORI_CERTBOT_RENEW_INTERVAL_SECONDS\n' >&2; exit 1 ;;
esac
[ "$renew_interval" -ge 3600 ] || {
  printf '❌ KAORI_CERTBOT_RENEW_INTERVAL_SECONDS must be at least 3600\n' >&2
  exit 1
}

issue() {
  printf '🔒 Requesting Let\047s Encrypt certificate · %s\n' "$domain"
  certbot certonly \
    --non-interactive \
    --agree-tos \
    --email "$email" \
    --webroot \
    --webroot-path "$webroot" \
    --domain "$domain" \
    --keep-until-expiring
  [ -s "$fullchain" ] && [ -s "$privkey" ] || {
    printf '❌ certificate files were not created\n' >&2
    return 1
  }
  printf '✅ Certificate available · %s\n' "$domain"
}

renew() {
  printf '🔒 Checking certificate renewal · %s\n' "$domain"
  certbot renew \
    --non-interactive \
    --webroot \
    --webroot-path "$webroot" \
    --quiet
  printf '✅ Certificate renewal check complete\n'
}

while :; do
  if [ -s "$fullchain" ] && [ -s "$privkey" ]; then
    renew || true
  else
    issue || true
  fi
  sleep "$renew_interval" &
  wait $! || true
done
