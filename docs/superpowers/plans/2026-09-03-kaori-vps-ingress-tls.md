# KAORI VPS Compose-Managed Ingress and TLS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the KAORI VPS public edge into the governed Docker Compose graph so `https://kaori.cloud` is served by Compose-managed Nginx + Certbot while KAORI web/PostgreSQL/Redis remain private.

**Architecture:** `compose.production.yml` keeps the application graph but removes web host publication. `deploy/vps/compose.vps.yml` adds immutable Nginx and Certbot services; Nginx proxies `web:5000`, Certbot shares persistent certificate/ACME volumes, and Nginx reloads itself when certificate material changes. Host responsibilities are limited to Docker, firewall/SSH policy, and DNS provider control.

**Tech Stack:** Docker Compose, Bash, Nginx, Certbot/Let's Encrypt HTTP-01, pytest contracts, GitHub Actions Developer Check/Full Admission.

**Spec:** `docs/superpowers/specs/2026-09-03-kaori-vps-ingress-tls-design.md`

## Global Constraints

- `kaori-deploy` remains non-sudo.
- KAORI `web` has no host-published port; Docker network access is `web:5000` only.
- PostgreSQL and Redis remain without host-published ports.
- Only Nginx publishes host 80/443.
- Nginx and Certbot images are digest-qualified.
- No Docker socket is mounted into any edge container.
- TLS private keys remain in a persistent Docker named volume.
- Unknown HTTP Host and TLS SNI traffic must not reach KAORI.
- Stable release promotion remains blocked until explicit human UAT acceptance.

---

### Task 1: Rewrite the ingress contract for Compose ownership

**Files:**
- Modify: `tests/contracts/release/test_vps_ingress_tls_contract.py`

**Interfaces:**
- Consumes: approved Compose-managed edge design.
- Produces: RED assertions for private web exposure, edge services, templates, edge scripts, immutable infrastructure images, and public verification.

- [ ] Assert `compose.production.yml` uses `expose: 5000` for `web` and no `ports:` entry in the web block.
- [ ] Assert `deploy/vps/compose.vps.yml` defines `nginx` and `certbot`, immutable image variables, only 80/443 host publication, persistent Let's Encrypt/ACME volumes, and no Docker socket.
- [ ] Assert final Nginx config proxies `http://web:5000`, rejects unknown Host/SNI, and uses TLS 1.2/1.3.
- [ ] Assert `nginx-entrypoint.sh`, `certbot-entrypoint.sh`, and `verify-ingress.sh` parse with `bash -n`/`sh -n` as appropriate and contain no host package/service mutation.
- [ ] Assert UAT workflow delivers `deploy/nginx` into the admitted release directory.
- [ ] Run Developer Check and capture RED before implementation.

### Task 2: Make KAORI web internal-only and add Compose edge services

**Files:**
- Modify: `compose.production.yml`
- Modify: `deploy/vps/compose.vps.yml`
- Modify: `.env.production.example`

**Interfaces:**
- Produces internal endpoint `web:5000`, public edge ports 80/443, and persistent certificate volumes.

- [ ] Replace the `web` host `ports` mapping with `expose: ["5000"]`.
- [ ] Add required persistent variables `KAORI_PUBLIC_DOMAIN`, `KAORI_PUBLIC_IP`, `KAORI_LETSENCRYPT_EMAIL`, `KAORI_NGINX_IMAGE`, and `KAORI_CERTBOT_IMAGE` to the production example.
- [ ] Remove the obsolete `KAORI_BIND_ADDRESS` example.
- [ ] Add `nginx` service with `80:8080`, `443:8443`, read-only root filesystem, dropped capabilities, `no-new-privileges`, shared certificate/ACME volumes, and `kaori_production` network.
- [ ] Add `certbot` service with shared writable certificate/ACME volumes, read-only root filesystem, dropped capabilities, no Docker socket, and `kaori_production` network.
- [ ] Add named volumes for Let's Encrypt and ACME state.

### Task 3: Implement container-native Nginx and Certbot lifecycle

**Files:**
- Create: `deploy/nginx/kaori-http.conf.template`
- Modify: `deploy/nginx/kaori.conf.template`
- Create: `deploy/nginx/nginx-entrypoint.sh`
- Create: `deploy/nginx/certbot-entrypoint.sh`
- Delete: `deploy/nginx/bootstrap-ingress.sh`
- Modify: `deploy/nginx/README.md`
- Modify/Delete: `deploy/nginx/kaori.conf.example` as a concise compatibility pointer only if retained.

**Interfaces:**
- Nginx entrypoint consumes `KAORI_PUBLIC_DOMAIN`, shared `/etc/letsencrypt`, and templates; it starts HTTP-only until certificate availability, then validates/reloads TLS.
- Certbot entrypoint consumes `KAORI_PUBLIC_DOMAIN`, `KAORI_LETSENCRYPT_EMAIL`, and shared webroot/certificate volumes; it performs first issuance and recurring renewals.

- [ ] HTTP-only config listens 8080, rejects unknown hosts, serves only the intended ACME path, and returns a non-success response for other intended-host paths until TLS exists.
- [ ] Final config listens 8080/8443, redirects intended HTTP traffic to HTTPS, rejects unknown Host/SNI, serves ACME, and proxies to `web:5000` with canonical forwarded headers.
- [ ] Nginx wrapper renders config, starts Nginx, detects certificate appearance/change, runs `nginx -t`, and reloads without Docker socket access.
- [ ] Certbot wrapper validates domain/email, obtains the first certificate with webroot, then runs renewal every 12 hours by default.

### Task 4: Extend deployment and verification

**Files:**
- Modify: `deploy/vps/deploy.sh`
- Modify: `deploy/vps/verify.sh`
- Modify: `deploy/nginx/verify-ingress.sh`

**Interfaces:**
- Deployment starts application health first, then edge services, then waits for public HTTPS before recording success.
- VPS verification proves containers/images/internal health/private exposure.
- Ingress verification proves DNS/redirect/TLS/HSTS/public health/unknown-host behavior.

- [ ] Add concise KAORI status markers (`🔎`, `🐳`, `💾`, `🗃️`, `🚀`, `🌐`, `🔒`, `🩺`, `✅`) without changing fail-closed semantics.
- [ ] Pull/start Nginx and Certbot only after `web` is healthy.
- [ ] Wait for ingress verification with a bounded timeout so initial ACME issuance can complete.
- [ ] Verify the web container health endpoint internally instead of `127.0.0.1:5000` on the host.
- [ ] Verify web/PostgreSQL/Redis publish no host ports and Nginx publishes only the approved edge ports.
- [ ] Verify digest-qualified configured Nginx/Certbot images.

### Task 5: Documentation, workflow formatting, and branch authority

**Files:**
- Modify: `deploy/vps/README.md`
- Modify: `deploy/nginx/README.md`
- Modify: `.github/workflows/deploy-uat-vps.yml` only as needed for canonical formatting/delivery.
- Modify: PR #130 body and Issue #50 evidence.

- [ ] Document exact host environment adjustments and firewall requirements.
- [ ] Ensure UAT workflow copies all edge scripts/templates into the exact admitted release directory.
- [ ] Make workflow YAML Prettier-clean.
- [ ] Run Developer Check until GREEN and mark PR #130 ready.
- [ ] Merge PR #130 to `kaori/staging` only after branch checks/review requirements are satisfied.
- [ ] Require exact staging Full Admission PASS before new UAT deployment authority.

### Task 6: Fresh RC, UAT deployment, and public evidence

**Files:**
- No source change unless runtime evidence finds a defect.
- Update Issue #50/#49 evidence.

- [ ] Confirm `/etc/kaori/.env.production` has the five new edge variables and immutable infrastructure image refs.
- [ ] Confirm public firewall TCP 80/443 is open and host Nginx/Apache is not already occupying those ports.
- [ ] Cut a fresh intentional RC from the admitted staging SHA.
- [ ] Move `kaori/uat-request` to that exact SHA and run the governed UAT deployment.
- [ ] Require public `https://kaori.cloud/health/ready` PASS with trusted certificate, HSTS, correct SAN/expiry, unknown Host/SNI rejection, and no public 5000/5432/6379.
- [ ] Capture Certbot renewal dry-run evidence before final UAT acceptance.
- [ ] Stop before Issue #51 until the maintainer explicitly accepts the exact SHA + immutable digest.
