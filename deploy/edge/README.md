# Shared Server Edge Gateway

`deploy/edge/` is the independent public-ingress and certificate-management boundary for a KAORI host. It is intentionally separate from the KAORI application Compose project so the same VPS can publish KAORI, n8n, and future applications without coupling their deployment lifecycles.

## Ownership

The shared edge owns:

- host TCP 80 and 443;
- Nginx and Certbot container lifecycle;
- the external Docker network `edge-public`;
- site registrations;
- ACME HTTP-01 webroot;
- Let's Encrypt certificate lineages;
- Nginx validation/reload;
- DNS, redirect, trusted TLS, readiness, unknown Host/SNI, and renewal verification.

KAORI owns none of those resources after cutover. KAORI `web` is only an upstream consumer using the stable network alias `kaori-web`.

## Host layout

```text
/opt/shared-edge/
├── config/
│   ├── edge.env
│   └── sites/
│       ├── kaori.env
│       └── <future-app>.env
├── state/
│   ├── letsencrypt/
│   ├── acme-webroot/
│   └── cutover-complete
└── releases/
    └── <admitted-sha>/deploy/edge/
```

The application remains under `/opt/kaori`. Shared-edge state is not stored in KAORI Compose volumes.

## Site registration

A published application joins the external Docker network `edge-public` and receives a stable upstream alias. Add one `*.env` file under `/opt/shared-edge/config/sites/`:

```dotenv
EDGE_DOMAIN=app.example.com
EDGE_UPSTREAM=app-edge
EDGE_UPSTREAM_PORT=8080
EDGE_TLS=true
EDGE_HEALTH_PATH=/health
EDGE_WEBSOCKET=false
EDGE_CLIENT_MAX_BODY_SIZE=25m
```

Do not add placeholder registrations to the active directory. Every active registration is expected to have real DNS and a reachable upstream.

The repository contains reviewed examples for KAORI and n8n under `deploy/edge/sites/`.

## Adding n8n

The n8n application Compose project remains independent. Attach only the n8n frontend service to `edge-public` with a stable alias such as `n8n`; do not publish host port 5678. Configure n8n's externally visible host/protocol/webhook settings for the HTTPS domain, then create the DNS A record and copy the reviewed n8n site registration with the real domain.

After DNS resolves to the VPS, run the shared-edge apply workflow. Certbot issues the domain certificate, Nginx detects the certificate state change, validates the complete configuration with `nginx -t`, and reloads without restarting KAORI or n8n.

## Initial KAORI migration

The first migration is intentionally two-phase.

### Prepare

`prepare.sh`:

1. creates `edge-public` if missing;
2. initializes `/opt/shared-edge/config/edge.env` from the existing KAORI deployment adapter only when the independent file does not exist;
3. creates the initial `kaori.env` registration;
4. copies the existing `kaori-vps-letsencrypt` lineage into shared-edge state when present;
5. validates the shared-edge Compose model;
6. does **not** bind or mutate host ports 80/443.

This preserves the currently trusted `kaori.cloud` certificate instead of forcing unnecessary issuance.

### Application handoff

Deploy the admitted KAORI release. The KAORI `web` container must join both `kaori-production` and `edge-public` as `kaori-web`. PostgreSQL, Redis, workers, and Beat remain only on the KAORI private network.

KAORI deployment deliberately does not use `--remove-orphans` during the migration window, so the existing legacy Nginx/Certbot containers can continue serving the site until edge cutover.

### Apply / cutover

`apply.sh`:

1. re-runs prepare idempotently;
2. proves `kaori-web` is attached to `edge-public`;
3. records the legacy KAORI Nginx/Certbot container identities;
4. stops only those legacy edge containers;
5. starts the shared edge on 80/443;
6. verifies every active site, immutable edge images, unknown Host/SNI rejection, and Certbot renewal dry-run;
7. restarts the legacy edge if shared-edge verification fails;
8. records `cutover-complete` only after successful verification.

Stopped legacy containers are retained after the first successful cutover as a deterministic emergency rollback asset. A later reviewed cleanup may retire them.

## Normal operation

After cutover:

- KAORI deploys do not start, stop, recreate, or configure Nginx/Certbot.
- n8n deploys do not change KAORI.
- adding a site changes only the application registration plus shared-edge apply.
- Nginx/Certbot never receive the Docker socket.
- Nginx runs read-only with only its required runtime capabilities.
- certificate state is writable by Certbot and read-only to Nginx.

The delivery authority is `.github/workflows/deploy-shared-edge.yml`. Push-based runs use `kaori/edge-request`, which must point to the exact admitted `kaori/staging` SHA. Manual runs must be dispatched from `kaori/staging`.

## Operator flow for another application

```text
Deploy application on its private network
        ↓
Attach only frontend to edge-public
        ↓
Create DNS A record → VPS public IP
        ↓
Add /opt/shared-edge/config/sites/<app>.env
        ↓
Run shared-edge apply
        ↓
Certbot issuance/renewal
        ↓
nginx -t
        ↓
atomic reload
        ↓
DNS / HTTPS / readiness verification
```

A KAORI application redeploy must not interrupt other registered applications, and an n8n redeploy must not interrupt KAORI ingress.
