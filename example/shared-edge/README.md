# Standalone Shared Public Edge Example

This directory is an **optional reference implementation**, not a KAORI runtime component.

KAORI is complete when its own application stack is healthy. Public DNS, Nginx, Certbot, host ports 80/443, and unrelated applications belong to a separate infrastructure lifecycle.

The example exists because KAORI is the first application currently published through this pattern on the VPS.

## Boundary

### KAORI owns

- its web application on port 5000;
- PostgreSQL and Redis;
- Celery workers and Beat;
- application configuration, migrations, health, and rollback.

KAORI does **not** require this directory, the `edge-public` network, Nginx, Certbot, public DNS, or trusted TLS to complete its own deployment.

### This standalone edge example owns

- host TCP 80 and 443;
- Nginx;
- Certbot / ACME HTTP-01;
- `edge-public`;
- public domain registrations;
- certificate state;
- public DNS/TLS/readiness verification.

Applications are attached to this edge only as an explicit **post-deploy publication operation**.

## Reference layout

Copy this example to an independently managed host path such as:

```text
/opt/shared-edge/
├── runtime/
│   ├── compose.yml
│   ├── nginx-entrypoint.sh
│   ├── certbot-entrypoint.sh
│   ├── prepare.sh
│   ├── publish-container.sh
│   ├── apply.sh
│   ├── verify.sh
│   └── kaori-cutover-example.sh
├── config/
│   ├── edge.env
│   └── sites/
└── state/
    ├── letsencrypt/
    └── acme-webroot/
```

The runtime directory can come from a reviewed repository checkout. Configuration and certificate state stay outside the KAORI application paths.

## 1. Configure the standalone edge

Copy `edge.env.example` to `/opt/shared-edge/config/edge.env` and set immutable image references plus host identity:

```dotenv
EDGE_NGINX_IMAGE=nginx:<reviewed-version>@sha256:<digest>
EDGE_CERTBOT_IMAGE=certbot/certbot:<reviewed-version>@sha256:<digest>
EDGE_LETSENCRYPT_EMAIL=operator@example.com
EDGE_PUBLIC_IP=<VPS_PUBLIC_IPV4>

EDGE_SITES_DIR=/opt/shared-edge/config/sites
EDGE_CERTIFICATE_DIR=/opt/shared-edge/state/letsencrypt
EDGE_ACME_WEBROOT_DIR=/opt/shared-edge/state/acme-webroot
```

Then run:

```bash
bash ./prepare.sh
```

`prepare.sh` validates the standalone edge configuration and creates `edge-public`. It does not inspect, start, stop, or modify KAORI.

## DNS authority and application onboarding

The standalone edge does **not** own authoritative DNS. Public records remain managed by the selected DNS provider or registrar.

The authority split is:

```text
DNS provider
    └── app.example.com → VPS public IPv4

standalone shared edge
    ├── domain registration → edge alias + upstream port
    ├── HTTP → HTTPS redirect
    ├── ACME HTTP-01 and certificate lifecycle
    ├── TLS termination
    └── reverse proxy / readiness verification

application
    └── owns only its internal service, health, data, and lifecycle
```

To publish a new application:

1. deploy the application independently and confirm its frontend container is healthy;
2. create or update the public DNS record so the domain resolves to `EDGE_PUBLIC_IP`;
3. run `publish-container.sh` to attach only the frontend container to `edge-public`, assign a stable alias, and write the site registration;
4. run `apply.sh` to reconcile Nginx/Certbot and verify DNS, redirect, trusted TLS, readiness, Host/SNI rejection, and certificate renewal;
5. after any frontend-container replacement, rerun `publish-container.sh` against the new healthy container because the host-side `edge-public` attachment is intentionally outside the application Compose lifecycle.

Active domain-to-upstream registrations are the files under:

```text
/opt/shared-edge/config/sites/*.env
```

Use those registrations as the operator-visible inventory of applications currently published through the edge. Do not hand-edit generated Nginx virtual-host files inside the edge container.

## 2. Publish any healthy application

The application must already be running and healthy independently.

Use `publish-container.sh` to attach only its frontend container to `edge-public` and create a domain registration.

Example shape:

```bash
bash ./publish-container.sh \
  --site-id my-app \
  --domain app.example.com \
  --container <running-container-id-or-name> \
  --alias my-app-edge \
  --port 8080 \
  --health-path /health \
  --tls true \
  --websocket false
```

This publication step does not restart the application.

Because the application does not declare `edge-public`, recreating its frontend container removes the host-side edge attachment. After any frontend-container replacement, rerun `publish-container.sh` against the new healthy container before relying on the public route. This rebinding remains an edge/publication operation and must not be hidden inside the application deployment.

After DNS points at the VPS:

```bash
bash ./apply.sh
```

The edge starts independently, issues/renews certificates, validates Nginx configuration, and verifies every active registration.

## KAORI publication example

KAORI itself does not declare `edge-public`.

When the standalone edge is used, the publication mapping is:

```text
kaori.cloud
    ↓
standalone Nginx
    ↓
edge-public
    ↓
kaori-web:5000
    ↓
KAORI web container
```

For a normal post-migration publication, locate the already-healthy KAORI web container and publish it:

```bash
KAORI_WEB="$(docker ps -q \
  --filter label=com.docker.compose.project=kaori-production \
  --filter label=com.docker.compose.service=web | head -n1)"

bash ./publish-container.sh \
  --site-id kaori \
  --domain kaori.cloud \
  --container "$KAORI_WEB" \
  --alias kaori-web \
  --port 5000 \
  --health-path /health/ready \
  --tls true \
  --websocket false \
  --client-max-body-size 25m
```

The repository file `sites/kaori.env.example` documents the resulting registration. After a future KAORI web-container recreation, locate the new healthy web container and rerun the same `publish-container.sh` command; KAORI deployment itself remains unaware of the public edge.

## One-time migration from the current KAORI-owned edge

The current VPS already has KAORI-owned Nginx/Certbot and an existing trusted certificate lineage.

`kaori-cutover-example.sh` is intentionally KAORI-specific and exists only for this one-time migration example. It:

1. verifies the current KAORI web container is healthy;
2. preserves the existing `kaori-vps-letsencrypt` certificate lineage when available;
3. attaches only the KAORI web frontend to `edge-public`;
4. creates the `kaori.cloud` registration;
5. stops only the legacy KAORI Nginx/Certbot containers;
6. starts and verifies the standalone edge;
7. restarts the legacy edge if the standalone cutover fails.

Run this only after the new KAORI release that no longer owns public edge services is deployed and healthy.

## n8n is only a second-consumer example

n8n is **not part of KAORI**.

The example demonstrates that an unrelated application can use the same standalone public gateway:

```text
auto.kaori.cloud
    ↓
standalone Nginx
    ↓
edge-public
    ↓
n8n:5678
    ↓
independent n8n application
```

The planned public domain is `auto.kaori.cloud`. The n8n application must be deployed and healthy independently before it is published.

For a reverse-proxied HTTPS deployment, configure the n8n application itself with values appropriate to its own stack, for example:

```dotenv
N8N_HOST=auto.kaori.cloud
N8N_PORT=5678
N8N_PROTOCOL=https
N8N_EDITOR_BASE_URL=https://auto.kaori.cloud
N8N_WEBHOOK_URL=https://auto.kaori.cloud/
N8N_PROXY_HOPS=1
```

Then publish only the n8n frontend container:

```bash
bash ./publish-container.sh \
  --site-id n8n \
  --domain auto.kaori.cloud \
  --container <n8n-container> \
  --alias n8n \
  --port 5678 \
  --health-path /healthz \
  --tls true \
  --websocket true \
  --client-max-body-size 50m

bash ./apply.sh
```

The repository file `sites/n8n.env.example` is reference documentation only. KAORI CI, deployment, runtime, and release do not depend on it.

## Security properties

The reference keeps the important ingress controls from the previous KAORI-owned edge:

- immutable Nginx and Certbot images;
- no Docker socket mounted into Nginx or Certbot;
- read-only Nginx root filesystem;
- dropped Linux capabilities with only required runtime capabilities restored;
- unknown Host/SNI rejection;
- unknown HTTP Host rejection;
- unknown TLS SNI rejection;
- TLS 1.2/1.3;
- HSTS;
- ACME HTTP-01;
- certificate renewal dry-run;
- Nginx configuration validation before reload;
- certificate state writable only by Certbot and read-only to Nginx.

## Scope rule

Do not add an application to KAORI because it uses this gateway.

The relationship is:

```text
KAORI ─┐
n8n   ─┼─ optional publication → standalone public edge
App N ─┘
```

Each application keeps its own lifecycle, data, deployment, health checks, rollback, and ownership.
