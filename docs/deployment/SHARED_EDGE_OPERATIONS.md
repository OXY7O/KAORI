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

## KAORI hostname separation (app domain vs website apex) — #2210

The intended split is `app.kaori.cloud` for the KAORI application and
`kaori.cloud` for the separately deployed landing-page website. Never
redirect the apex to the app as a permanent policy. Existing `auto.kaori.cloud`
remains an independent shared-edge consumer.

1. Complete an immutable KAORI deployment and internal web admission before
   attempting public publication. Ensure the initial UAT-only PostgreSQL
   bootstrap and schema-cutover flags are both `false` for subsequent releases.
2. Confirm authoritative DNS for `app.kaori.cloud` points to the
   `EDGE_PUBLIC_IP` on the shared edge. Check A, unexpected AAAA and relevant
   CAA records/HTTP-01 reachability; do not change the edge deployment host.
3. Prepare a protected `/etc/kaori/app.env` rollback copy. Configure
   `KAORI_PUBLIC_BASE_URL=https://app.kaori.cloud` and
   `TRUSTED_HOSTS=app.kaori.cloud,localhost`. The prior `kaori.cloud` may
   remain in `TRUSTED_HOSTS` for a *time-bounded* compatibility window only,
   if the old site must continue routing app requests. Preserve ProxyFix
   trust-counts and all other settings.
4. An environment-file edit alone does **not** replace the environment of
   existing Docker containers. Apply this configuration only as part of a
   separately admitted governed deployment/recreation of the KAORI runtime.
   Confirm the new web container is healthy and still has restricted DB
   credentials. Do not manually patch generated Nginx configuration.
5. The reviewed Staging Publication workflow reads and validates
   `KAORI_PUBLIC_BASE_URL` and `TRUSTED_HOSTS` from the host's application
   authority. It uses the existing `publish-container.sh` to update site ID
   `kaori` at `app.kaori.cloud` with alias `kaori-web:5000`, and
   `apply.sh` to issue/reconcile its trusted TLS certificate and verify
   every active registration.
6. Before the new hostname replaces an existing apex site registration,
   preserve the working shared-edge site configuration, TLS state and
   recovery procedure. **Certbot renewal dry-run covers retained certificate
   lineages**, including an older `kaori.cloud` lineage. Keep apex HTTP-01
   challenge routing available through an explicitly managed temporary legacy
   site until the landing-page site takes ownership, or retire the stale
   lineage only under a reviewed edge recovery procedure. Never delete
   certificates merely to make renewal verification green.
7. Verify `https://app.kaori.cloud/health/ready`, HTTP to HTTPS,
   certificate SAN/chain, HSTS, unknown Host/SNI refusal,
   `auto.kaori.cloud` readiness and Certbot renewal dry-run. Verify
   generated app links, login, and authorization under the new public URL.
   Keep public publication evidence independent from KAORI deploy success.

**Rollback:** if the new site fails, restore the protected original
`/etc/kaori/app.env` during a governed app rollback/redeploy; restore
the previous shared-edge registration using the same
`publish-container.sh` authority and run `apply.sh` and `verify.sh`.
Changing `app.env` in place without restarting its web container does not
rollback the active application's Host policy. Do not restart PostgreSQL,
Redis or workers solely to repair a standalone edge publication failure.

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

## New TLS site discovery and Certbot lock recovery — #2212

The standalone edge's **installed** runtime under `/opt/shared-edge/runtime` is
a separate operating authority from the reviewed example in the KAORI repo.
Do not assume an application RC deploy copies example scripts to that host.

### Host-runtime parity (before adding a new TLS site)

From a **reviewed, immutable checkout of the accepted shared-edge source**
available to the edge operator, compare the installed Certbot entrypoint:

```bash
REVIEWED_EDGE=/path/to/reviewed/KAORI/example/shared-edge
diff -u "$REVIEWED_EDGE/certbot-entrypoint.sh" \
  /opt/shared-edge/runtime/certbot-entrypoint.sh
diff -u "$REVIEWED_EDGE/verify.sh" \
  /opt/shared-edge/runtime/verify.sh
```

The current Certbot entrypoint rescans all TLS site registrations every
`EDGE_CERTBOT_ISSUE_RETRY_SECONDS` (30s default). The independent
`EDGE_CERTBOT_RENEW_INTERVAL_SECONDS` (43200s default) limits full renewal
checks and **must not** postpone new hostname discovery.

A previous installed host runtime used `sleep "$renew_interval"` after a
successful scan. On 2026-10-16 it skipped a new `app.kaori.cloud` registration
until the operator restarted only Certbot, causing temporary fail-closed HTTP
503 while the certificate was absent. This is an **installed runtime drift**
finding; the current source already uses the shorter site-discovery interval.

If there is a mismatch, **hold any new domain publication** and perform a
separately approved standalone-edge maintenance operation: back up the installed
script(s), check the reviewed checkout's accepted SHA and file diff, install
only the reviewed files with preserved owner/mode and atomic replacement, then
restart only the affected standalone edge service when necessary. The existing
Certbot process does not reload its entrypoint from the bind mount while it
is running. Never copy `edge.env`, active site registrations, Let's Encrypt
state, or ACME webroot from a checkout, and never restart unrelated KAORI/n8n
services to perform this maintenance. Verify three domains afterward.

### Concurrent Certbot renewal dry-run

A manual `verify.sh --renewal-dry-run` and a GitHub publication job can overlap
an automatic or manually started Certbot invocation. The existing shared-edge
verifier retries **only** the exact Certbot exclusive-lock diagnostic
`Another instance of Certbot is already running.`, up to 12 attempts with
15 seconds between attempts; the verifier still requires a successful real
`certbot renew --dry-run` run to PASS.

Other Certbot errors (ACME validation, authorization, rate limits,
configuration, storage) fail immediately. Persistent locking fails after
the bounded retries and must not be bypassed or converted into a warning.
Avoid running the manual verifier concurrently with GitHub publication.
Do not delete lock files, disable TLS checks, or restart the application to
avoid the collision.

If app deployment succeeded but publication failed, let any active operator
dry-run finish, then rerun **only** the failed Publication Reconciliation job,
preserving the same admitted immutable RC and separate application evidence.

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
