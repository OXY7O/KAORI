#!/bin/sh
set -eu

sites_dir="${EDGE_SITES_DIR:-/etc/shared-edge/sites}"
reload_interval="${EDGE_RELOAD_INTERVAL_SECONDS:-30}"
active_dir=/etc/nginx/conf.d

case "$reload_interval" in
  ''|*[!0-9]*) printf '❌ invalid EDGE_RELOAD_INTERVAL_SECONDS\n' >&2; exit 1 ;;
esac
[ "$reload_interval" -ge 5 ] || {
  printf '❌ EDGE_RELOAD_INTERVAL_SECONDS must be at least 5\n' >&2
  exit 1
}
[ -d "$sites_dir" ] || {
  printf '❌ shared-edge site directory is missing: %s\n' "$sites_dir" >&2
  exit 1
}

load_site() {
  site_file="$1"
  EDGE_DOMAIN=''
  EDGE_UPSTREAM=''
  EDGE_UPSTREAM_PORT=''
  EDGE_TLS='true'
  EDGE_HEALTH_PATH='/'
  EDGE_WEBSOCKET='false'
  EDGE_CLIENT_MAX_BODY_SIZE='25m'
  # shellcheck source=/dev/null
  . "$site_file"

  printf '%s\n' "$EDGE_DOMAIN" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$' || {
    printf '❌ invalid EDGE_DOMAIN in %s\n' "$site_file" >&2
    return 1
  }
  printf '%s\n' "$EDGE_UPSTREAM" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*$' || {
    printf '❌ invalid EDGE_UPSTREAM in %s\n' "$site_file" >&2
    return 1
  }
  case "$EDGE_UPSTREAM_PORT" in
    ''|*[!0-9]*) printf '❌ invalid EDGE_UPSTREAM_PORT in %s\n' "$site_file" >&2; return 1 ;;
  esac
  [ "$EDGE_UPSTREAM_PORT" -ge 1 ] && [ "$EDGE_UPSTREAM_PORT" -le 65535 ] || {
    printf '❌ EDGE_UPSTREAM_PORT out of range in %s\n' "$site_file" >&2
    return 1
  }
  case "$EDGE_TLS" in true|false) ;; *) printf '❌ EDGE_TLS must be true or false in %s\n' "$site_file" >&2; return 1 ;; esac
  case "$EDGE_WEBSOCKET" in true|false) ;; *) printf '❌ EDGE_WEBSOCKET must be true or false in %s\n' "$site_file" >&2; return 1 ;; esac
  case "$EDGE_HEALTH_PATH" in /*) ;; *) printf '❌ EDGE_HEALTH_PATH must start with / in %s\n' "$site_file" >&2; return 1 ;; esac
  printf '%s\n' "$EDGE_CLIENT_MAX_BODY_SIZE" | grep -Eq '^[0-9]+[kKmMgG]?$' || {
    printf '❌ invalid EDGE_CLIENT_MAX_BODY_SIZE in %s\n' "$site_file" >&2
    return 1
  }
}

certificate_ready() {
  domain="$1"
  [ -s "/etc/letsencrypt/live/$domain/fullchain.pem" ] &&
    [ -s "/etc/letsencrypt/live/$domain/privkey.pem" ]
}

append_proxy_location() {
  out="$1"
  cat >> "$out" <<EOF
    location / {
        resolver 127.0.0.11 valid=30s ipv6=off;
        resolver_timeout 5s;
        set \$edge_upstream "http://$EDGE_UPSTREAM:$EDGE_UPSTREAM_PORT";
        proxy_pass \$edge_upstream;
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
EOF
  if [ "$EDGE_TLS" = 'true' ]; then
    printf '%s\n' '        proxy_set_header X-Forwarded-Port 443;' >> "$out"
  else
    printf '%s\n' '        proxy_set_header X-Forwarded-Port 80;' >> "$out"
  fi
  if [ "$EDGE_WEBSOCKET" = 'true' ]; then
    cat >> "$out" <<'EOF'
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
EOF
  fi
  cat >> "$out" <<'EOF'

        proxy_connect_timeout 10s;
        proxy_send_timeout 90s;
        proxy_read_timeout 90s;
        proxy_buffering on;
    }
EOF
}

render_site() {
  site_file="$1"
  target_dir="$2"
  load_site "$site_file"
  site_id="$(basename "$site_file" .env | sed 's/[^A-Za-z0-9_.-]/_/g')"
  out="$target_dir/10-$site_id.conf"

  if [ "$EDGE_TLS" = 'true' ] && certificate_ready "$EDGE_DOMAIN"; then
    cat > "$out" <<EOF
server {
    listen 8080;
    server_name $EDGE_DOMAIN;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
        try_files \$uri =404;
    }

    location / {
        return 301 https://$EDGE_DOMAIN\$request_uri;
    }
}

server {
    listen 8443 ssl;
    http2 on;
    server_name $EDGE_DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$EDGE_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$EDGE_DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SHARED_EDGE_TLS:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    client_max_body_size $EDGE_CLIENT_MAX_BODY_SIZE;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
EOF
    append_proxy_location "$out"
    printf '%s\n' '}' >> "$out"
    return
  fi

  if [ "$EDGE_TLS" = 'true' ]; then
    cat > "$out" <<EOF
server {
    listen 8080;
    server_name $EDGE_DOMAIN;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
        try_files \$uri =404;
    }

    location / {
        return 503;
    }
}
EOF
    return
  fi

  cat > "$out" <<EOF
server {
    listen 8080;
    server_name $EDGE_DOMAIN;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
        try_files \$uri =404;
    }

    client_max_body_size $EDGE_CLIENT_MAX_BODY_SIZE;
EOF
  append_proxy_location "$out"
  printf '%s\n' '}' >> "$out"
}

render_all() {
  target_dir="$1"
  rm -f "$target_dir"/*.conf
  cat > "$target_dir/00-default.conf" <<'EOF'
server {
    listen 8080 default_server;
    server_name _;
    return 444;
}

server {
    listen 8443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
}
EOF

  site_count=0
  for site_file in "$sites_dir"/*.env; do
    [ -f "$site_file" ] || continue
    render_site "$site_file" "$target_dir"
    site_count=$((site_count + 1))
  done
  [ "$site_count" -gt 0 ] || {
    printf '❌ no active shared-edge site registrations found in %s\n' "$sites_dir" >&2
    return 1
  }
}

state_signature() {
  {
    for site_file in "$sites_dir"/*.env; do
      [ -f "$site_file" ] || continue
      cksum "$site_file"
      load_site "$site_file"
      if [ "$EDGE_TLS" = 'true' ]; then
        for certificate_file in           "/etc/letsencrypt/live/$EDGE_DOMAIN/fullchain.pem"           "/etc/letsencrypt/live/$EDGE_DOMAIN/privkey.pem"; do
          if [ -s "$certificate_file" ]; then
            cksum "$certificate_file"
          else
            printf 'missing %s\n' "$certificate_file"
          fi
        done
      fi
    done
  } | cksum | awk '{print $1 ":" $2}'
}

install_rendered_config() {
  rendered_dir="$1"
  backup_dir="$(mktemp -d /tmp/shared-edge-nginx-backup.XXXXXX)"
  cp -a "$active_dir/." "$backup_dir/" 2>/dev/null || true
  rm -f "$active_dir"/*.conf
  cp "$rendered_dir"/*.conf "$active_dir/"

  if nginx -t; then
    rm -rf "$backup_dir"
    return 0
  fi

  printf '❌ rendered shared-edge configuration failed nginx -t; restoring prior config\n' >&2
  rm -f "$active_dir"/*.conf
  cp -a "$backup_dir/." "$active_dir/" 2>/dev/null || true
  rm -rf "$backup_dir"
  nginx -t
  return 1
}

initial_render="$(mktemp -d /tmp/shared-edge-nginx-render.XXXXXX)"
render_all "$initial_render"
install_rendered_config "$initial_render"
rm -rf "$initial_render"

nginx -g 'daemon off;' &
nginx_pid=$!

terminate() {
  kill -TERM "$nginx_pid" 2>/dev/null || true
  wait "$nginx_pid" 2>/dev/null || true
}
trap terminate INT TERM HUP

last_signature="$(state_signature)"
printf '✅ Shared-edge Nginx started with reconciled site configuration\n'

while kill -0 "$nginx_pid" 2>/dev/null; do
  sleep "$reload_interval" &
  wait $! || true

  current_signature="$(state_signature)"
  [ "$current_signature" = "$last_signature" ] && continue

  rendered_dir="$(mktemp -d /tmp/shared-edge-nginx-render.XXXXXX)"
  if render_all "$rendered_dir" && install_rendered_config "$rendered_dir"; then
    nginx -s reload
    last_signature="$current_signature"
    printf '✅ Shared-edge Nginx reload PASS\n'
  else
    printf '❌ Shared-edge Nginx reconciliation rejected; prior config remains active\n' >&2
  fi
  rm -rf "$rendered_dir"
done

wait "$nginx_pid"
