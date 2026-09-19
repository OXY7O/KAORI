# KAORI Compose Edge

This directory owns the **Compose-managed Nginx + Certbot edge** used by the KAORI VPS UAT runtime. Nginx and Certbot are part of the governed Docker Compose project; the VPS does not require a separate host-managed Nginx or Certbot service.

## Target path

```text
Internet :80/:443
        ↓
Compose-managed Nginx
        ↓
Docker network
        ↓
web:5000
        ↓
KAORI
```

Only Nginx publishes public ports. KAORI web, PostgreSQL, and Redis stay private to the Compose network and must not expose host listeners on 5000, 5432, or 6379.

## Runtime authority

The deployment adapter is `/etc/kaori/deploy.env`. It must identify the reviewed public endpoint and immutable infrastructure images:

```dotenv
KAORI_PUBLIC_DOMAIN=kaori.cloud
KAORI_PUBLIC_IP=62.171.187.206
KAORI_LETSENCRYPT_EMAIL=<reviewed-acme-email>
KAORI_NGINX_IMAGE=nginx@sha256:<reviewed-digest>
KAORI_CERTBOT_IMAGE=certbot/certbot@sha256:<reviewed-digest>
```

PostgreSQL and Redis image authorities are stored in the same deployment adapter as `KAORI_POSTGRES_IMAGE` and `KAORI_REDIS_IMAGE`. Application behavior remains in `/etc/kaori/app.env`, secrets remain in `/etc/kaori/secrets.env`, and active release identity is generated at `/var/lib/kaori/deploy-state/release.env` only after successful deployment verification.

The GitHub UAT workflow may supply `KAORI_LETSENCRYPT_EMAIL` as a reviewed deployment override. `deploy.sh` keeps the persistent deployment adapter as the default authority while allowing that explicit workflow value to override the email for the candidate transaction.

## DNS

Initial UAT authority is the apex only:

```text
Type:  A
Name:  @
Value: 62.171.187.206
```

`kaori.cloud` must resolve to the reviewed VPS IPv4 before certificate issuance. `www.kaori.cloud` is outside the initial certificate contract.

## Compose lifecycle

`deploy/vps/deploy.sh` owns the governed sequence. After immutable application/image evidence, database safety, migration, and application readiness have passed, it starts the edge services:

```text
🐳 immutable application/infrastructure images
✅ PostgreSQL / Redis private readiness
💾 pre-migration backup when required
🗃️ migration
🚀 KAORI application services
🩺 internal web-container readiness
🌐 Nginx HTTP ACME edge
🔒 Certbot certificate issue / renewal
🔄 Nginx TLS activation / reload
🩺 public HTTPS readiness
✅ release identity promotion
```

Nginx bootstraps the ACME HTTP-01 path before the certificate exists. Certbot writes certificate material into the shared persistent certificate volume. Nginx detects the certificate and activates the TLS configuration. Renewal runs inside the Certbot service; the Nginx entrypoint detects certificate changes and reloads without Docker socket access.

## Nginx authority

The reviewed configuration surfaces are:

- `kaori-http.conf.template` — HTTP-only ACME bootstrap state;
- `kaori.conf.template` — final TLS reverse proxy to `web:5000`;
- `nginx-entrypoint.sh` — renders the appropriate configuration and reloads when certificate state changes;
- `certbot-entrypoint.sh` — certificate issuance and renewal loop;
- `verify-ingress.sh` — public/private ingress acceptance.

Do not publish `web:5000` on the VPS to make Nginx work. Container-to-container routing must use the Docker network service name `web:5000`.

## Verification

The deployment transaction runs the verifier automatically. For an admitted release checkout it can also be executed explicitly:

```bash
bash deploy/nginx/verify-ingress.sh \
  --domain kaori.cloud \
  --expected-ip 62.171.187.206 \
  --renewal-dry-run
```

The verifier requires:

- DNS contains `62.171.187.206`;
- HTTP redirects to the exact HTTPS path;
- the public TLS certificate is trusted, contains `DNS:kaori.cloud`, and has more than seven days remaining;
- HSTS is present;
- `https://kaori.cloud/health/ready` passes;
- the KAORI web container passes its internal readiness check;
- host listeners do not expose 5000, 5432, or 6379;
- running Nginx and Certbot images match `KAORI_NGINX_IMAGE` and `KAORI_CERTBOT_IMAGE` immutable digests;
- unknown HTTP Host and TLS SNI are rejected;
- the Certbot renewal dry-run passes when requested.

## Host boundary

Compose manages the application edge, but it does not replace host governance. The VPS/provider firewall must permit public TCP 80 and 443 and keep private application/state ports closed. SSH, the Docker daemon, kernel/network policy, and administrative account hardening remain host responsibilities.

Do not give `kaori-deploy` sudo merely to manage ingress; Compose edge lifecycle does not require that privilege escalation. Docker-group membership remains root-equivalent and must stay treated as a privileged deployment boundary.

## UAT acceptance boundary

A successful `https://kaori.cloud` check is necessary but not sufficient for stable promotion. Issue #50 must retain exact staging SHA, RC tag, OCI digest, DNS/TLS/renewal evidence, private-port proof, and the successful governed UAT deployment run. Human UAT must then explicitly accept that exact source SHA and digest before Issue #51 may promote `kaori/staging` to `main`.
