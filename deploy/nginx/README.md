# KAORI Host Ingress

This directory owns the root-managed public ingress boundary for the KAORI VPS. Ordinary application releases continue through `deploy/vps/` as `kaori-deploy`; that account intentionally remains non-sudo and does not manage Nginx, certificates, DNS, or host firewall policy.

## Target path

```text
Internet :80/:443
        ↓
Host Nginx
        ↓
127.0.0.1:5000
        ↓
KAORI web
```

PostgreSQL and Redis remain on the private Compose network and must not have host listeners.

## 1. DNS

The initial UAT hostname is the apex only:

```text
Type:  A
Name:  @
Value: 62.171.187.206
TTL:   300 seconds during UAT, or the provider default
```

Do not request a certificate until public DNS resolves `kaori.cloud` to `62.171.187.206`. `bootstrap-ingress.sh` also verifies that the resolved IPv4 is assigned to the VPS and fails closed when DNS is stale or points elsewhere.

`www.kaori.cloud` is not part of the initial certificate or ingress contract.

## 2. Repository admission

Run host changes only from an admitted KAORI revision. The #50 branch first passes Developer Check, merges to `kaori/staging`, and then requires exact staging Full Admission before the scripts below become UAT authority.

Do not copy `kaori.conf.example` into `/etc/nginx`. The canonical configuration is `kaori.conf.template`, rendered by the bootstrap script.

## 3. Root bootstrap

The full KAORI Compose runtime must already be healthy at:

```text
http://127.0.0.1:5000/health/ready
```

Then, from the admitted repository checkout on the VPS, run as root:

```bash
bash deploy/nginx/bootstrap-ingress.sh \
  --domain kaori.cloud \
  --email '<operator-acme-email>'
```

The script performs these stages in order:

```text
🩺 loopback KAORI readiness
🌐 DNS-to-this-VPS admission
📦 Nginx/Certbot prerequisite installation when needed
✅ HTTP-only ACME bootstrap config + nginx -t
🔒 Let's Encrypt HTTP-01 certificate issuance/retention
✅ final HTTPS reverse-proxy config + nginx -t
🔒 Certbot renewal timer + renew --dry-run
```

It never adds `kaori-deploy` to an administrative group and never edits SSH authorization policy.

## 4. Verify

After bootstrap:

```bash
bash deploy/nginx/verify-ingress.sh \
  --domain kaori.cloud \
  --expected-ip 62.171.187.206
```

The verifier requires:

- DNS includes the reviewed VPS IPv4;
- HTTP redirects exactly to HTTPS;
- the public certificate is trusted, contains `DNS:kaori.cloud`, and has more than seven days remaining;
- HSTS is present;
- `https://kaori.cloud/health/ready` passes;
- `http://127.0.0.1:5000/health/ready` still passes;
- port 5000 is not bound beyond loopback;
- ports 5432 and 6379 are not host listeners;
- an unknown HTTP Host is rejected;
- an unknown TLS SNI handshake is rejected.

## 5. Firewall and external evidence

Nginx does not replace the VPS/provider firewall. Public UAT requires TCP 80 and 443 to reach this VPS. SSH remains a separately governed management path.

Before UAT acceptance, verify externally that no unexpected application/state service is reachable. In particular, public access to 5000, 5432, 6379, or a Docker API is prohibited.

Do not disable root SSH merely to satisfy a checklist while `kaori-deploy` is the only non-root account available for deployment: it intentionally has no sudo. Establish and test a separate sudo-capable management identity first, then perform SSH daemon hardening as a dedicated host-admin change so administrative access cannot be locked out.

## 6. Renewal

`bootstrap-ingress.sh` enables `certbot.timer` when the distribution exposes that unit and requires:

```bash
certbot renew --dry-run
```

to pass during initial ingress admission. Periodically confirm the timer remains active:

```bash
systemctl status certbot.timer
```

## UAT acceptance boundary

Public HTTPS availability is necessary but not sufficient for stable promotion. Issue #50 must record DNS, Nginx, certificate/renewal, public readiness, unknown-host rejection and external exposure evidence. The maintainer must then explicitly accept the exact source SHA and immutable RC digest before Issue #51 may promote `kaori/staging` to `main`.
