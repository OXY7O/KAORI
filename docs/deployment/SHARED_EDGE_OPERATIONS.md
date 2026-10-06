# KAORI Shared-Edge Operations Procedure

This runbook is the operational authority for publishing an already-healthy KAORI deployment through the independently managed standalone shared edge. It complements `example/shared-edge/README.md`; it does not move Nginx, Certbot, public DNS, TLS, host ports 80/443, or `edge-public` into the KAORI application lifecycle.

## Ownership boundary

KAORI application deployment ends when the governed application stack is healthy internally.

The standalone shared edge separately owns:

- host TCP 80 and 443;
- Nginx and Certbot;
- the external `edge-public` Docker network;
- public site registrations under `/opt/shared-edge/config/sites`;
- ACME HTTP-01 webroot and certificate state;
- DNS/TLS/public-readiness verification.

A public-edge failure must not rewrite an otherwise successful KAORI application release state. Repair publication and rerun publication reconciliation instead of redeploying KAORI unless application health itself is degraded.

## Required host layout

The governed host layout is:

```text
/opt/shared-edge/
├── runtime/
│   ├── compose.yml
│   ├── nginx-entrypoint.sh
│   ├── certbot-entrypoint.sh
│   ├── prepare.sh
│   ├── publish-container.sh
│   ├── apply.sh
│   └── verify.sh
├── config/
│   ├── edge.env
│   └── sites/
└── state/
    ├── letsencrypt/
    └── acme-webroot/
```

`/opt/shared-edge/config/edge.env` contains shared-edge infrastructure configuration and remains private. Use mode `0600` when only one host identity needs access, or `0640` with a dedicated deployment/read group when governed automation must read it.

Files under `/opt/shared-edge/config/sites/*.env` contain routing metadata only. They must be mode `0644` so read-only bind mounts remain readable by Nginx/Certbot when Docker uses a remapped or non-root container identity.

The sites directory may be group-writable for the governed deployment identity:

```bash
sudo chown root:"$KAORI_GROUP" /opt/shared-edge/config/sites
sudo chmod 2770 /opt/shared-edge/config/sites
```

Do not make `edge.env` world-readable.

## Normal post-deploy publication

After a governed UAT/staging deployment succeeds, publication must:

1. locate the current healthy `kaori-production` web container;
2. attach only that container to `edge-public`;
3. ensure alias `kaori-web`;
4. write/update `/opt/shared-edge/config/sites/kaori.env`;
5. apply the shared edge;
6. verify DNS, HTTP redirect, trusted TLS, readiness, Host/SNI rejection, immutable edge images, and Certbot renewal dry-run.

The KAORI application Compose stack must not declare `edge-public`.

## Manual recovery procedure

Use this only when KAORI application deployment is already healthy and public publication failed.

### 1. Confirm application health

```bash
KAORI_WEB="$(docker ps -q \
  --filter label=com.docker.compose.project=kaori-production \
  --filter label=com.docker.compose.service=web | head -n1)"

test -n "$KAORI_WEB"

docker inspect --format \
  'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{end}}' \
  "$KAORI_WEB"
```

Expected:

```text
status=running health=healthy
```

Do not continue with edge repair if the application itself is unhealthy.

### 2. Validate shared-edge permissions

```bash
KAORI_USER=kaori-deploy
KAORI_GROUP="$(id -gn "$KAORI_USER")"

sudo -u "$KAORI_USER" test -r /opt/shared-edge/config/edge.env
sudo -u "$KAORI_USER" test -w /opt/shared-edge/config/sites

sudo stat -c '%U %G %a %n' \
  /opt/shared-edge/config/edge.env \
  /opt/shared-edge/config/sites
```

Expected policy:

```text
edge.env      600 or 640
config/sites  setgid + writable by governed deployment group
```

Normalize existing site registrations:

```bash
sudo find /opt/shared-edge/config/sites \
  -maxdepth 1 \
  -type f \
  -name '*.env' \
  -exec chmod 0644 {} \;
```

### 3. Validate standalone edge runtime

```bash
cd /opt/shared-edge/runtime
sudo -u "$KAORI_USER" bash ./prepare.sh
```

Expected:

```text
Standalone edge prepare PASS
```

### 4. Verify host port publication

The Nginx container listens internally on 8080/8443 and Docker publishes those ports on host 80/443.

```bash
docker inspect shared-edge-example-nginx-1 \
  --format 'PortBindings={{json .HostConfig.PortBindings}}'

sudo ss -ltnp | grep -E ':(80|443)\b'
```

Expected Docker binding:

```text
8080/tcp -> host 80
8443/tcp -> host 443
```

If Docker shows correct bindings but the host has no listeners, inspect Nginx before changing Compose:

```bash
docker logs --tail 100 shared-edge-example-nginx-1
```

A permission error reading `/etc/shared-edge/sites/*.env` means the registration file mode is wrong. Normalize registrations to `0644`; do not widen `edge.env`.

### 5. Recreate only shared-edge services when required

```bash
cd /opt/shared-edge/runtime

docker compose \
  --env-file /opt/shared-edge/config/edge.env \
  --project-directory /opt/shared-edge/runtime \
  -f compose.yml \
  up -d --pull never --force-recreate nginx certbot
```

Do not restart PostgreSQL, Redis, KAORI workers, or the KAORI web container solely for a publication repair.

### 6. Verify public readiness

```bash
cd /opt/shared-edge/runtime
bash ./verify.sh --wait-seconds 360 --renewal-dry-run
```

Required PASS evidence:

- DNS resolves to the configured public IPv4;
- HTTP redirects to HTTPS;
- trusted TLS is served;
- `https://kaori.cloud/health/ready` is healthy;
- every other active shared-edge registration is healthy;
- Nginx/Certbot run reviewed immutable images;
- unknown Host/SNI is rejected;
- Certbot renewal dry-run succeeds.

Because `verify.sh` validates every active site registration, a broken unrelated registration remains a shared-edge operational failure and must be repaired rather than ignored.

## ACME HTTP-01 troubleshooting

If redirect and HTTPS readiness pass but Certbot renewal dry-run reports `connection refused`, validate public HTTP-01 reachability.

```bash
sudo ss -ltnp | grep -E ':(80|443)\b'

docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep shared-edge

sudo ufw status verbose 2>/dev/null || true
sudo nft list ruleset 2>/dev/null | grep -E -C3 'dport (80|443)' || true
sudo iptables -L INPUT -n -v 2>/dev/null | grep -E 'dpt:(80|443)' || true
```

If the host listens on 80/443 and local firewall policy allows them, verify the VPS/provider firewall permits inbound TCP 80 and 443.

To validate the ACME webroot externally:

```bash
sudo mkdir -p /opt/shared-edge/state/acme-webroot/.well-known/acme-challenge
printf 'kaori-acme-test\n' | sudo tee \
  /opt/shared-edge/state/acme-webroot/.well-known/acme-challenge/kaori-test \
  >/dev/null
```

From a machine outside the VPS network:

```bash
curl -fsS http://kaori.cloud/.well-known/acme-challenge/kaori-test
```

Expected:

```text
kaori-acme-test
```

Remove the probe afterward:

```bash
sudo rm -f /opt/shared-edge/state/acme-webroot/.well-known/acme-challenge/kaori-test
```

Do not disable renewal dry-run merely to make publication green.

## GitHub recovery rule

When deployment already succeeded and only post-deploy publication failed:

- do not create a new RC solely for the edge failure;
- do not redeploy KAORI solely for the edge failure;
- repair the standalone edge prerequisite;
- rerun only the failed Publication Reconciliation job when safe;
- retain the same immutable RC/source SHA evidence;
- record recovery evidence in the owning issue.

A new application source SHA still requires the normal Developer Check -> staging Full Admission -> RC -> UAT flow.

## Completion evidence

A shared-edge publication incident is resolved only when:

- KAORI web remains running and healthy;
- the current web container is attached to `edge-public` with alias `kaori-web`;
- `kaori.cloud` registration exists and is readable by edge containers;
- host TCP 80/443 listeners are active;
- DNS, redirect, TLS, and readiness pass;
- every active site registration passes shared-edge verification;
- Certbot renewal dry-run passes;
- governed Publication Reconciliation completes successfully;
- no KAORI application rollback/redeploy was performed solely to hide an edge-only failure.

## Related authorities

- `example/shared-edge/README.md`
- `example/shared-edge/publish-container.sh`
- `example/shared-edge/apply.sh`
- `example/shared-edge/verify.sh`
- `.github/workflows/deploy-staging-host.yml`
- `.github/workflows/reconcile-staging-publication.yml`
- `docs/deployment/CI_CD_RECOVERY_CONTRACT.md`
- issue #527
