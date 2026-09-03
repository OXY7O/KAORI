# KAORI VPS Ingress and TLS Design

## Context

Issue #49 has produced successful UAT runtime evidence for `v0.1.0-rc.5` at source `9720be872ed1aad4efcaabee43870bd741a202dd` using immutable image `docker.io/lethisaputri/kaori@sha256:149cbd8e88dcc2b520e498010b4296eb37960e0b924bd2b120d3f649c595d048`. The full Compose graph is healthy and the web service is reachable only at `127.0.0.1:5000` on the VPS.

Issue #50 owns the next boundary: expose KAORI at `https://kaori.cloud` without changing the application deployment trust model.

## Goals

- Serve KAORI at `https://kaori.cloud` through host Nginx.
- Keep KAORI web bound to `127.0.0.1:5000` and keep PostgreSQL/Redis without host-published ports.
- Obtain and renew a publicly trusted certificate through Certbot webroot validation.
- Redirect the intended hostname from HTTP to HTTPS while preserving ACME challenge access.
- Reject unknown HTTP Host and TLS SNI traffic rather than forwarding it to KAORI.
- Preserve proxy identity headers required by KAORI and avoid weakening application-owned CSP/security policy.
- Provide deterministic host-side and external verification commands suitable for UAT evidence.
- Keep host administration root-owned; do not add `kaori-deploy` to sudo and do not use Docker-group privilege as an ingress-management shortcut.

## Non-goals

- Application release deployment remains owned by `deploy/vps/` and the governed `kaori-deploy` SSH path.
- Stable `main` promotion remains Issue #51.
- DNS-provider mutation is not performed by repository scripts because the DNS control-plane credential/provider is not part of the KAORI repository trust boundary.
- SSH daemon hardening must not disable root access until a separate sudo-capable management identity has been verified. The current `kaori-deploy` account intentionally has no sudo access.

## Architecture

```text
Internet
   |
   | TCP 80 / 443
   v
Host Nginx
   |-- unknown Host/SNI -> reject
   |-- /.well-known/acme-challenge/ -> local ACME webroot
   `-- kaori.cloud HTTPS -> http://127.0.0.1:5000
                               |
                               v
                            KAORI web

PostgreSQL / Redis -> private Compose network only
```

Nginx and certificate lifecycle are host infrastructure. Normal KAORI RC deployments never rewrite Nginx configuration, certificates, DNS, or firewall policy.

## Repository surfaces

### `deploy/nginx/kaori.conf.template`

Canonical Nginx configuration rendered by the root bootstrap script. It contains:

- default port 80 host rejection;
- default TLS SNI rejection with `ssl_reject_handshake on`;
- dedicated `kaori.cloud` port 80 ACME/redirect server;
- dedicated `kaori.cloud` TLS server;
- TLS 1.2/1.3 only;
- reverse proxy to `127.0.0.1:5000`;
- canonical `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-Port` headers;
- request/body and upstream timeout controls;
- HSTS after TLS is active;
- no replacement CSP header.

### `deploy/nginx/bootstrap-ingress.sh`

Idempotent, root-only Ubuntu/Debian operator script. Required inputs:

- `--domain` — expected public hostname, currently `kaori.cloud`;
- `--email` — ACME registration/renewal contact.

Optional inputs:

- `--upstream` — defaults to `127.0.0.1:5000`;
- `--acme-webroot` — defaults to `/var/www/kaori-acme`.

The script validates the local KAORI readiness endpoint before changing ingress, installs/verifies Nginx and Certbot, installs an HTTP bootstrap configuration, obtains the certificate via webroot, installs the final TLS configuration, validates with `nginx -t`, reloads Nginx, enables Certbot renewal, and performs a renewal dry run.

The script fails closed if DNS does not resolve the configured hostname to an address present on the host before requesting a certificate. This prevents accidental certificate attempts against stale DNS.

The script does not edit SSH daemon policy and does not grant sudo privileges to `kaori-deploy`.

### `deploy/nginx/verify-ingress.sh`

Read-only verification usable by root or an ordinary operator. It verifies:

- DNS resolution exists;
- HTTP redirects to the expected HTTPS hostname;
- HTTPS readiness succeeds;
- certificate SAN contains the expected hostname;
- certificate is not near expiry;
- HSTS exists;
- KAORI remains reachable on loopback;
- port 5000 is not bound to a non-loopback host address;
- PostgreSQL/Redis standard ports are not host listeners;
- unknown Host HTTP traffic is not forwarded to KAORI;
- unknown TLS SNI is rejected.

## DNS boundary

Before certificate issuance, the DNS provider must contain:

```text
Type: A
Name: @
Value: 62.171.187.206
TTL: provider default / 300 seconds during UAT
```

If `www.kaori.cloud` is desired later, it is a separate explicit hostname and certificate decision. Initial UAT scope is apex `kaori.cloud` only.

The host bootstrap must refuse certificate issuance until `kaori.cloud` resolves to the target VPS.

## TLS model

Certbot uses HTTP-01 webroot validation. Nginx serves only `/.well-known/acme-challenge/` over HTTP for the expected hostname; all other expected-host HTTP requests redirect to HTTPS. Unknown hosts are rejected.

The certificate paths are the standard Certbot paths under `/etc/letsencrypt/live/<domain>/`. Renewal uses the distribution Certbot systemd timer when available. A `certbot renew --dry-run` is required before ingress setup is considered complete.

## Security boundaries

- `kaori-deploy` remains non-sudo.
- Application port 5000 remains loopback-only.
- No host PostgreSQL/Redis publication is introduced.
- Nginx must not proxy unknown Host/SNI traffic.
- Nginx does not replace KAORI CSP.
- TLS private keys remain under `/etc/letsencrypt` with root-managed permissions.
- Repository contains templates/scripts only, never generated certificates or DNS credentials.
- Firewall/SSH hardening is validated separately. SSH root login is not disabled until a sudo-capable management identity exists, avoiding administrative lockout.

## Failure behavior

- Missing root privilege -> stop.
- Unsupported OS -> stop.
- Invalid domain/email/upstream input -> stop.
- Local KAORI readiness failure -> stop before ingress mutation.
- DNS mismatch -> stop before ACME request.
- Nginx syntax failure -> do not reload.
- Certificate issuance failure -> keep the HTTP bootstrap configuration so ACME can be retried; do not install a broken TLS server.
- TLS verification or renewal dry-run failure -> report failure and do not claim ingress completion.

## Acceptance evidence

Ingress UAT is complete only when evidence records:

1. `kaori.cloud` resolves to `62.171.187.206`.
2. `http://kaori.cloud` redirects to HTTPS.
3. `https://kaori.cloud/health/ready` succeeds with a publicly trusted certificate.
4. Unknown Host/SNI is rejected.
5. `127.0.0.1:5000/health/ready` still succeeds locally.
6. Port 5000 is loopback-only and PostgreSQL/Redis are not host listeners.
7. Certbot renewal dry-run passes.
8. External port/TLS/DAST checks have no unexplained high/critical finding.

Explicit human UAT acceptance of the exact SHA + immutable digest remains required before Issue #51 promotion.