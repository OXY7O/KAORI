#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/kaori.conf.template"
SITE_AVAILABLE='/etc/nginx/sites-available/kaori.conf'
SITE_ENABLED='/etc/nginx/sites-enabled/kaori.conf'
LOCAL_READY_URL='http://127.0.0.1:5000/health/ready'

domain=''
email=''
acme_webroot='/var/www/kaori-acme'

fail() {
  printf '❌ KAORI ingress bootstrap failed · %s\n' "$*" >&2
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
  sudo bash deploy/nginx/bootstrap-ingress.sh --domain DOMAIN --email EMAIL [options]

Required:
  --domain DOMAIN          Public KAORI hostname, for example kaori.cloud.
  --email EMAIL            ACME registration and renewal contact.

Options:
  --acme-webroot PATH      ACME HTTP-01 webroot (default: /var/www/kaori-acme).
  -h, --help               Show this help.

This is a root-owned host-infrastructure operation. Normal KAORI application
releases remain owned by the non-sudo kaori-deploy deployment path.
USAGE
}

while (($#)); do
  case "$1" in
    --domain)
      (($# >= 2)) || fail '--domain requires a value'
      domain="${2,,}"
      shift 2
      ;;
    --email)
      (($# >= 2)) || fail '--email requires a value'
      email="$2"
      shift 2
      ;;
    --acme-webroot)
      (($# >= 2)) || fail '--acme-webroot requires a value'
      acme_webroot="$2"
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

(( EUID == 0 )) || fail 'run this script as root'
[[ -n "$domain" ]] || fail '--domain is required'
[[ -n "$email" ]] || fail '--email is required'
[[ "$domain" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]] || \
  fail 'domain contains unsupported characters or labels'
[[ "$email" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || fail 'email is not a valid ACME contact shape'
[[ "$acme_webroot" =~ ^/[A-Za-z0-9._/-]+$ && "$acme_webroot" != '/' ]] || fail 'ACME webroot must be a safe absolute path below /'
[[ -f "$TEMPLATE" && ! -L "$TEMPLATE" ]] || fail "canonical Nginx template is missing: $TEMPLATE"

[[ -f /etc/os-release ]] || fail '/etc/os-release is required'
# shellcheck source=/dev/null
source /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) fail "unsupported distribution: ${ID:-unknown}; supported hosts are Ubuntu and Debian" ;;
esac

for required_command in apt-get getent awk sort grep sed install systemctl; do
  command -v "$required_command" >/dev/null 2>&1 || fail "$required_command is required"
done

install_ingress_packages() {
  local missing=false
  for command_name in nginx certbot curl openssl ip; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      missing=true
      break
    fi
  done

  if [[ "$missing" == 'true' ]]; then
    status '📦' 'Installing Nginx, Certbot, and ingress verification prerequisites'
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y nginx certbot ca-certificates curl openssl iproute2
  else
    status '✅' 'Ingress packages already available'
  fi
}

verify_local_runtime() {
  status '🩺' "Checking KAORI loopback readiness · $LOCAL_READY_URL"
  curl --fail --silent --show-error --max-time 10 "$LOCAL_READY_URL" >/dev/null || \
    fail 'KAORI loopback readiness must pass before ingress mutation'
  status '✅' 'KAORI loopback readiness PASS'
}

verify_dns_targets_this_host() {
  local -a resolved_ips=()
  local -a host_ips=()
  local resolved_ip host_ip matched=false

  status '🌐' "Resolving $domain before ACME admission"
  mapfile -t resolved_ips < <(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)
  ((${#resolved_ips[@]} > 0)) || fail "$domain has no IPv4 DNS resolution"

  mapfile -t host_ips < <(ip -4 -o addr show scope global | awk '{split($4, address, "/"); print address[1]}' | sort -u)
  ((${#host_ips[@]} > 0)) || fail 'the VPS has no globally scoped IPv4 address'

  for resolved_ip in "${resolved_ips[@]}"; do
    for host_ip in "${host_ips[@]}"; do
      if [[ "$resolved_ip" == "$host_ip" ]]; then
        matched=true
        break 2
      fi
    done
  done

  if [[ "$matched" != 'true' ]]; then
    printf 'Resolved IPv4: %s\n' "${resolved_ips[*]}" >&2
    printf 'Host IPv4: %s\n' "${host_ips[*]}" >&2
    fail "$domain does not resolve to an IPv4 assigned to this VPS"
  fi

  status '✅' "DNS points to this VPS · ${resolved_ips[*]}"
}

render_http_bootstrap() {
  local destination="$1"
  cat > "$destination" <<'NGINX'
# Temporary HTTP-only KAORI ACME bootstrap. Replaced after certificate issuance.
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}

server {
    listen 80;
    listen [::]:80;
    server_name __KAORI_DOMAIN__;

    location ^~ /.well-known/acme-challenge/ {
        root __KAORI_ACME_WEBROOT__;
        default_type text/plain;
        try_files $uri =404;
    }

    location / {
        return 503;
    }
}
NGINX
  sed -i \
    -e "s|__KAORI_DOMAIN__|$domain|g" \
    -e "s|__KAORI_ACME_WEBROOT__|$acme_webroot|g" \
    "$destination"
}

render_final_config() {
  local destination="$1"
  sed \
    -e "s|__KAORI_DOMAIN__|$domain|g" \
    -e "s|__KAORI_ACME_WEBROOT__|$acme_webroot|g" \
    "$TEMPLATE" > "$destination"
}

install_site_config() {
  local source_file="$1"
  install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled
  install -m 0644 -o root -g root "$source_file" "$SITE_AVAILABLE"
  rm -f /etc/nginx/sites-enabled/default
  ln -sfn "$SITE_AVAILABLE" "$SITE_ENABLED"
  nginx -t
}

obtain_certificate() {
  status '🔒' "Requesting/retaining ACME certificate · $domain"
  certbot certonly \
    --non-interactive \
    --agree-tos \
    --email "$email" \
    --webroot \
    --webroot-path "$acme_webroot" \
    --domain "$domain" \
    --keep-until-expiring
  [[ -s "/etc/letsencrypt/live/$domain/fullchain.pem" ]] || fail 'certificate full chain was not created'
  [[ -s "/etc/letsencrypt/live/$domain/privkey.pem" ]] || fail 'certificate private key was not created'
  status '✅' 'ACME certificate available'
}

verify_renewal() {
  if systemctl list-unit-files --type=timer certbot.timer 2>/dev/null | grep -q '^certbot.timer'; then
    systemctl enable --now certbot.timer
    status '✅' 'Certbot renewal timer enabled'
  else
    status '⚠️' 'No certbot.timer unit found; certbot package renewal hook remains distribution-managed'
  fi

  status '🔒' 'Running Certbot renewal dry-run'
  certbot renew --dry-run
  status '✅' 'Certbot renewal dry-run PASS'
}

install_ingress_packages
verify_local_runtime
verify_dns_targets_this_host

install -d -m 0755 -o root -g root "$acme_webroot/.well-known/acme-challenge"
http_config="$(mktemp)"
final_config="$(mktemp)"
cleanup() {
  rm -f -- "$http_config" "$final_config"
}
trap cleanup EXIT INT TERM HUP

render_http_bootstrap "$http_config"
install_site_config "$http_config"
systemctl enable --now nginx
systemctl reload nginx
status '✅' 'HTTP ACME bootstrap active'

obtain_certificate
render_final_config "$final_config"
install_site_config "$final_config"
systemctl reload nginx
status '✅' 'Nginx HTTPS reverse proxy active'

verify_renewal

printf '\n✅ KAORI ingress bootstrap PASS\n'
printf '🌐 Domain      %s\n' "$domain"
printf '➡️ Upstream    %s\n' 'http://127.0.0.1:5000'
printf '🔒 Certificate %s\n' "/etc/letsencrypt/live/$domain/fullchain.pem"
printf '🩺 Next         bash deploy/nginx/verify-ingress.sh --domain %s\n' "$domain"
