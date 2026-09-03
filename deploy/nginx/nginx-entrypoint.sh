#!/bin/sh
set -eu

domain="${KAORI_PUBLIC_DOMAIN:?KAORI_PUBLIC_DOMAIN is required}"
reload_interval="${KAORI_NGINX_RELOAD_INTERVAL_SECONDS:-30}"
http_template=/etc/kaori-nginx/kaori-http.conf.template
tls_template=/etc/kaori-nginx/kaori.conf.template
active_config=/etc/nginx/conf.d/default.conf
fullchain="/etc/letsencrypt/live/$domain/fullchain.pem"
privkey="/etc/letsencrypt/live/$domain/privkey.pem"

case "$reload_interval" in
  ''|*[!0-9]*) printf '❌ invalid KAORI_NGINX_RELOAD_INTERVAL_SECONDS\n' >&2; exit 1 ;;
esac
[ "$reload_interval" -ge 5 ] || {
  printf '❌ KAORI_NGINX_RELOAD_INTERVAL_SECONDS must be at least 5\n' >&2
  exit 1
}

render() {
  template="$1"
  temporary="${active_config}.new"
  sed "s|__KAORI_DOMAIN__|$domain|g" "$template" > "$temporary"
  mv "$temporary" "$active_config"
}

certificate_ready() {
  [ -s "$fullchain" ] && [ -s "$privkey" ]
}

certificate_signature() {
  cksum "$fullchain" "$privkey" | cksum | awk '{print $1 ":" $2}'
}

last_signature=''
if certificate_ready; then
  printf '🔒 TLS material found · starting HTTPS configuration\n'
  render "$tls_template"
  mode=tls
  last_signature="$(certificate_signature)"
else
  printf '🌐 TLS material pending · starting ACME HTTP bootstrap\n'
  render "$http_template"
  mode=http
fi

nginx -t
nginx -g 'daemon off;' &
nginx_pid=$!

terminate() {
  kill -TERM "$nginx_pid" 2>/dev/null || true
  wait "$nginx_pid" 2>/dev/null || true
}
trap terminate INT TERM HUP

while kill -0 "$nginx_pid" 2>/dev/null; do
  sleep "$reload_interval" &
  wait $! || true

  if certificate_ready; then
    current_signature="$(certificate_signature)"
    if [ "$mode" = http ]; then
      printf '🔒 Certificate detected · enabling KAORI HTTPS\n'
      render "$tls_template"
      nginx -t
      nginx -s reload
      mode=tls
      last_signature="$current_signature"
      printf '✅ Nginx TLS reload PASS\n'
    elif [ "$current_signature" != "$last_signature" ]; then
      printf '🔄 Renewed certificate detected · reloading Nginx\n'
      nginx -t
      nginx -s reload
      last_signature="$current_signature"
      printf '✅ Nginx certificate reload PASS\n'
    fi
  fi
done

wait "$nginx_pid"
