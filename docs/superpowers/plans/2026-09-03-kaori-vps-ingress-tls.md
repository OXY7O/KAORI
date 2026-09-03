# KAORI VPS Ingress and TLS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the admitted KAORI UAT runtime safely at `https://kaori.cloud` through host Nginx with publicly trusted TLS and deterministic ingress verification.

**Architecture:** Host Nginx terminates HTTP/TLS and proxies only the intended hostname to the existing loopback KAORI web service at `127.0.0.1:5000`. Root-owned ingress provisioning is separate from ordinary `kaori-deploy` application releases, and verification covers both internal loopback health and public HTTPS behavior.

**Tech Stack:** Bash, Nginx, Certbot/Let's Encrypt HTTP-01, Docker Compose runtime evidence, pytest contract tests, GitHub Actions Developer Check.

**Spec:** `docs/superpowers/specs/2026-09-03-kaori-vps-ingress-tls-design.md`

## Global Constraints

- `kaori-deploy` remains non-sudo and is not used to mutate host Nginx/TLS policy.
- KAORI web remains bound to `127.0.0.1:5000`.
- PostgreSQL and Redis remain private with no host-published ports.
- Unknown HTTP Host and TLS SNI traffic must not reach KAORI.
- TLS is limited to TLS 1.2 and 1.3.
- Nginx must not replace or weaken the application CSP.
- DNS-provider credentials are not added to the repository.
- Stable release promotion remains blocked until explicit human UAT acceptance.

---

### Task 1: Lock the ingress security contract

**Files:**
- Create: `tests/contracts/release/test_vps_ingress_tls_contract.py`
- Test: `tests/contracts/release/test_vps_ingress_tls_contract.py`

**Interfaces:**
- Consumes: current `deploy/nginx/kaori.conf.example`, `compose.production.yml`, and Issue #50 architecture.
- Produces: contract assertions for the canonical Nginx template, root bootstrap, and read-only verifier.

- [ ] **Step 1: Write failing contract tests**

Assert that the intended implementation files exist and enforce:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NGINX_TEMPLATE = ROOT / "deploy/nginx/kaori.conf.template"
BOOTSTRAP = ROOT / "deploy/nginx/bootstrap-ingress.sh"
VERIFY = ROOT / "deploy/nginx/verify-ingress.sh"


def test_ingress_template_rejects_unknown_hosts_and_proxies_only_loopback():
    text = NGINX_TEMPLATE.read_text()
    assert "listen 80 default_server" in text
    assert "ssl_reject_handshake on" in text
    assert "proxy_pass http://127.0.0.1:5000" in text
    assert "ssl_protocols TLSv1.2 TLSv1.3" in text
    assert "Content-Security-Policy" not in text


def test_bootstrap_is_root_owned_and_requires_dns_before_acme():
    text = BOOTSTRAP.read_text()
    assert "EUID" in text
    assert "--domain" in text
    assert "--email" in text
    assert "getent ahostsv4" in text
    assert "certbot certonly" in text
    assert "certbot renew --dry-run" in text


def test_verifier_checks_public_https_and_private_runtime_boundary():
    text = VERIFY.read_text()
    assert "https://$domain/health/ready" in text
    assert "127.0.0.1:5000/health/ready" in text
    assert "openssl s_client" in text
    assert "5432" in text
    assert "6379" in text
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
pytest -q tests/contracts/release/test_vps_ingress_tls_contract.py
```

Expected: FAIL because the new canonical template/bootstrap/verifier do not yet exist.

- [ ] **Step 3: Commit the RED test**

```bash
git add tests/contracts/release/test_vps_ingress_tls_contract.py
git commit -m "test(deploy): lock VPS ingress and TLS contract #50"
```

---

### Task 2: Add the hardened Nginx template

**Files:**
- Create: `deploy/nginx/kaori.conf.template`
- Modify: `deploy/nginx/kaori.conf.example`
- Test: `tests/contracts/release/test_vps_ingress_tls_contract.py`

**Interfaces:**
- Consumes: placeholders `__KAORI_DOMAIN__` and `__KAORI_ACME_WEBROOT__` rendered by `bootstrap-ingress.sh`.
- Produces: final host Nginx configuration for the intended hostname.

- [ ] **Step 1: Implement the minimum template required by the RED assertions**

Template requirements:

```nginx
upstream kaori_web {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}

server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
}
```

Add the intended-host HTTP ACME/redirect server and TLS reverse proxy server. Use `ssl_protocols TLSv1.2 TLSv1.3`, standard Certbot certificate paths, HSTS, proxy identity headers, a 25 MiB request limit, and finite upstream timeouts. Do not add a CSP header.

- [ ] **Step 2: Keep `kaori.conf.example` as a concise operator pointer**

Replace the stale standalone example with a short note directing operators to render/install `kaori.conf.template` through `bootstrap-ingress.sh` so there is one configuration authority.

- [ ] **Step 3: Run focused tests**

```bash
pytest -q tests/contracts/release/test_vps_ingress_tls_contract.py
```

Expected: bootstrap/verifier assertions still fail; template assertions pass.

- [ ] **Step 4: Commit**

```bash
git add deploy/nginx/kaori.conf.template deploy/nginx/kaori.conf.example
git commit -m "feat(deploy): add hardened KAORI Nginx ingress template #50"
```

---

### Task 3: Add root-owned ingress bootstrap

**Files:**
- Create: `deploy/nginx/bootstrap-ingress.sh`
- Test: `tests/contracts/release/test_vps_ingress_tls_contract.py`

**Interfaces:**
- Consumes: `deploy/nginx/kaori.conf.template`, `--domain`, `--email`, optional `--upstream`, optional `--acme-webroot`.
- Produces: `/etc/nginx/sites-available/kaori.conf`, symlink under `sites-enabled`, Let's Encrypt certificate, enabled/reloaded Nginx, Certbot renewal proof.

- [ ] **Step 1: Implement input and host validation**

The script must:

```bash
set -Eeuo pipefail
(( EUID == 0 )) || fail 'run this script as root'
```

Validate Ubuntu/Debian, domain syntax, email presence, `127.0.0.1:<port>` upstream syntax, required commands, and local readiness `http://127.0.0.1:5000/health/ready` before ingress mutation.

- [ ] **Step 2: Implement DNS fail-closed admission**

Resolve with:

```bash
mapfile -t resolved_ips < <(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)
```

Collect host IPv4 addresses with `ip -4 -o addr show scope global`. Require at least one resolved address to match a host address before certificate issuance.

- [ ] **Step 3: Install/prepare host ingress packages and paths**

Use `apt-get` on Ubuntu/Debian to install `nginx`, `certbot`, `ca-certificates`, `curl`, and `openssl` only when required. Prepare the ACME webroot and Nginx site paths with root ownership.

- [ ] **Step 4: Install HTTP bootstrap safely**

Render a temporary HTTP-only config that rejects unknown hosts and serves `/.well-known/acme-challenge/` for the configured domain while proxying nothing publicly. Run `nginx -t` before reload.

- [ ] **Step 5: Obtain the certificate**

Use:

```bash
certbot certonly --non-interactive --agree-tos \
  --email "$email" --webroot -w "$acme_webroot" -d "$domain"
```

- [ ] **Step 6: Render final TLS config and verify renewal**

Render the canonical template placeholders, run `nginx -t`, reload Nginx, enable/start the Certbot timer when available, then run:

```bash
certbot renew --dry-run
```

- [ ] **Step 7: Run focused tests and shell syntax checks**

```bash
bash -n deploy/nginx/bootstrap-ingress.sh
pytest -q tests/contracts/release/test_vps_ingress_tls_contract.py
```

Expected: only verifier assertions remain RED.

- [ ] **Step 8: Commit**

```bash
git add deploy/nginx/bootstrap-ingress.sh tests/contracts/release/test_vps_ingress_tls_contract.py
git commit -m "feat(deploy): bootstrap KAORI Nginx and TLS ingress #50"
```

---

### Task 4: Add deterministic ingress verification

**Files:**
- Create: `deploy/nginx/verify-ingress.sh`
- Test: `tests/contracts/release/test_vps_ingress_tls_contract.py`

**Interfaces:**
- Consumes: `--domain`, optional `--expected-ip`.
- Produces: human-readable PASS evidence or a fail-closed nonzero exit.

- [ ] **Step 1: Implement DNS, redirect, HTTPS and certificate checks**

Use `getent`, `curl`, and `openssl`. Validate the certificate SAN through:

```bash
openssl s_client -connect "$domain:443" -servername "$domain" </dev/null 2>/dev/null \
  | openssl x509 -noout -checkend 604800
```

Also inspect SAN output and require `DNS:$domain`.

- [ ] **Step 2: Implement runtime exposure checks**

Require local loopback readiness. Inspect listening sockets with `ss -lnt` and fail if `:5000` is bound to a non-loopback address or if `:5432`/`:6379` are host listeners.

- [ ] **Step 3: Implement unknown Host/SNI rejection probes**

Send an HTTP request to loopback Nginx with an invalid Host and require that it is not proxied. Probe TLS with invalid SNI via `openssl s_client` and require handshake rejection.

- [ ] **Step 4: Add concise status output**

Use the KAORI terminal vocabulary:

```text
🌐 DNS
➡️ HTTP redirect
🔒 TLS
🩺 HTTPS readiness
🔐 Unknown host/SNI
✅ Ingress PASS
```

- [ ] **Step 5: Verify GREEN**

```bash
bash -n deploy/nginx/verify-ingress.sh
pytest -q tests/contracts/release/test_vps_ingress_tls_contract.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add deploy/nginx/verify-ingress.sh tests/contracts/release/test_vps_ingress_tls_contract.py
git commit -m "feat(deploy): verify KAORI public ingress and TLS #50"
```

---

### Task 5: Document the operator boundary and run the wide Developer Check

**Files:**
- Create: `deploy/nginx/README.md`
- Modify: `deploy/vps/README.md`
- Test: existing release contracts plus `test_vps_ingress_tls_contract.py`

**Interfaces:**
- Consumes: host bootstrap/verifier created above.
- Produces: exact DNS record, root commands, verification commands, and issue evidence expectations.

- [ ] **Step 1: Document DNS and root execution**

Document the required A record:

```text
kaori.cloud -> 62.171.187.206
```

Then document:

```bash
sudo bash deploy/nginx/bootstrap-ingress.sh \
  --domain kaori.cloud \
  --email '<operator-acme-email>'

bash deploy/nginx/verify-ingress.sh \
  --domain kaori.cloud \
  --expected-ip 62.171.187.206
```

Explain that `kaori-deploy` is intentionally not sudo-capable and application deploys do not manage ingress.

- [ ] **Step 2: Run focused quality**

```bash
python -m ruff check tests/contracts/release/test_vps_ingress_tls_contract.py
python -m ruff format --check tests/contracts/release/test_vps_ingress_tls_contract.py
pytest -q tests/contracts/release/test_vps_ingress_tls_contract.py
bash -n deploy/nginx/bootstrap-ingress.sh deploy/nginx/verify-ingress.sh
```

- [ ] **Step 3: Open PR to `kaori/staging` and use Developer Check as branch authority**

Developer Check must exercise workflow lint plus wide release contracts because the change touches `deploy/` and release contracts. Do not treat work-branch checks as staging Full Admission.

- [ ] **Step 4: After review merge, require exact staging Full Admission**

Only after exact `kaori/staging` KAORI CI passes may host ingress tooling be treated as admitted repository authority.

---

### Task 6: Apply ingress on UAT VPS and record public evidence

**Files:**
- No repository code change unless runtime evidence reveals a defect.
- Update: Issue #50 evidence/comment/checklist.

**Interfaces:**
- Consumes: admitted #50 scripts, operator-controlled DNS, root access to the VPS.
- Produces: public `https://kaori.cloud` UAT endpoint and evidence.

- [ ] **Step 1: Verify DNS provider record**

Require apex A record `kaori.cloud -> 62.171.187.206` and wait only until public resolvers return that value. Do not request certificates against stale DNS.

- [ ] **Step 2: Run the admitted root bootstrap on the VPS**

Execute `bootstrap-ingress.sh` as root with the operator ACME email.

- [ ] **Step 3: Run the admitted verifier**

Require all verifier stages to PASS.

- [ ] **Step 4: Run external HTTPS/port/TLS checks**

From outside the VPS, confirm HTTP redirect, valid HTTPS, expected hostname, no public 5000/5432/6379, and no unexpected public service exposure.

- [ ] **Step 5: Record Issue #50 evidence**

Record exact source SHA, RC digest, DNS result, certificate identity/expiry, renewal dry-run, Nginx test, HTTPS readiness, unknown-host rejection and public-port evidence.

- [ ] **Step 6: Stop before stable promotion**

Explicit human UAT acceptance is still required before Issue #51 may promote staging to `main`.