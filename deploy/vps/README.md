# KAORI VPS deployment

`deploy/vps/` owns KAORI application deployment to the single UAT/production-like VPS. It is intentionally separate from `ops/github-runner/`, which owns only GitHub self-hosted runner host lifecycle.

The application graph remains defined by `compose.production.yml`. This directory adds private PostgreSQL/Redis services and the operator surfaces required to deploy, verify, back up, restore, and roll back an immutable KAORI image.

## Security and ownership model

- Use a dedicated non-root deploy user for normal operations. Docker access is root-equivalent privilege and must be granted deliberately.
- SSH is key-only. The GitHub deployment workflow uses the encrypted RSA private key and passphrase from GitHub Secrets plus a pinned known-hosts record. Do not disable host-key verification.
- Registry credentials come from GitHub Secrets and are consumed for each deployment with `docker login --password-stdin` and an ephemeral Docker configuration directory.
- The real production environment file exists only on the VPS at `/etc/kaori/.env.production`. Never commit it or publish it as an Actions artifact.
- PostgreSQL, Redis, and the Docker API are not published to the Internet. KAORI web remains bound to `127.0.0.1:5000`; public ingress is owned by `deploy/nginx/` and Issue #50.
- Deployment accepts an immutable digest reference only, for example `registry.example/kaori@sha256:<64-hex-digest>`.

## One-time VPS preparation

Install Docker Engine and the Docker Compose plugin through the approved host-management process. Prepare the deploy user, then create the KAORI directories with ownership assigned to that user:

```bash
sudo install -d -m 0755 /etc/kaori
sudo install -d -m 0700 -o <deploy-user> -g <deploy-user> /var/lib/kaori/deploy-state
sudo install -d -m 0700 -o <deploy-user> -g <deploy-user> /var/lib/kaori/backups
sudo install -d -m 0755 -o <deploy-user> -g <deploy-user> /opt/kaori/releases
```

Create the real environment from the repository template, on the server only:

```bash
sudo install -m 0600 -o <deploy-user> -g <deploy-user> .env.production.example /etc/kaori/.env.production
sudoedit /etc/kaori/.env.production
```

The resulting file must remain mode `600`.

For the VPS Compose topology, configure at least these state variables in `/etc/kaori/.env.production`:

```text
POSTGRES_DB=kaori
POSTGRES_USER=kaori
POSTGRES_PASSWORD=<strong-random-url-safe-value>
REDIS_PASSWORD=<strong-random-url-safe-value>
DATABASE_URL=postgresql://kaori:<same-postgres-password>@postgres:5432/kaori
REDIS_URL=redis://:<same-redis-password>@redis:6379/0
CELERY_BROKER_URL=redis://:<same-redis-password>@redis:6379/1
RATELIMIT_STORAGE_URI=redis://:<same-redis-password>@redis:6379/2
CELERY_RESULT_BACKEND=redis://:<same-redis-password>@redis:6379/3
KAORI_PUBLIC_BASE_URL=https://kaori.cloud
TRUSTED_HOSTS=kaori.cloud,127.0.0.1,localhost
KAORI_BIND_ADDRESS=127.0.0.1
KAORI_PORT=5000
```

Use URL-safe random passwords or URL-encode credentials before embedding them in connection URLs. Populate all other application, S3/MinIO, authentication, and integration values from `.env.production.example` according to the environment being deployed.

Do not leave `ADMIN_PASSWORD` populated after the first administrator bootstrap. First-install administrator creation remains an explicit operator action after migration and before general UAT access.

## GitHub Environment configuration

Prefer an Environment named `uat` for deployment credentials and approval policy. Configure these Secrets:

- `KAORI_VPS_SSH_PRIVATE_KEY`
- `KAORI_VPS_SSH_PASSPHRASE`
- `KAORI_VPS_SSH_KNOWN_HOSTS`
- `KAORI_DOCKER_REGISTRY_USERNAME`
- `KAORI_DOCKER_REGISTRY_PASSWORD`

Configure these repository or Environment variables:

- `KAORI_VPS_HOST`
- `KAORI_VPS_USER`
- `KAORI_VPS_PORT` (normally `22`)
- `KAORI_VPS_DEPLOY_ROOT` (optional; defaults to `/opt/kaori`)

`KAORI_VPS_SSH_KNOWN_HOSTS` must contain the reviewed host-key line for the exact VPS endpoint. Do not obtain and trust a new key automatically during deployment.

## Compose topology

Deployments combine:

```text
compose.production.yml
+ deploy/vps/compose.vps.yml
```

The overlay adds:

- PostgreSQL 16 with named volume `kaori-vps-postgres`;
- Redis 7 with named volume `kaori-vps-redis`, append-only persistence, and password authentication.

Neither service has a `ports` mapping. They are reachable only on the private KAORI Compose network.

## Deployment lifecycle

The manual GitHub workflow `.github/workflows/deploy-uat-vps.yml` is the normal remote entry point. It must be dispatched from the accepted `kaori/staging` ref and supplied with:

- the exact admitted staging source SHA;
- the exact registry image using an immutable digest.

The remote `deploy.sh` then performs:

1. immutable image/source validation;
2. server environment validation, including mode `600`;
3. ephemeral registry login and exact digest pull;
4. PostgreSQL/Redis startup and health verification;
5. KAORI production environment validation;
6. mandatory pre-migration PostgreSQL backup when an existing application schema is present;
7. one-shot migration;
8. startup of the full KAORI web/worker/Beat graph;
9. `verify.sh` health and `127.0.0.1:5000/health/ready` verification;
10. deployment evidence update in `/var/lib/kaori/deploy-state`.

The state directory records the current and previous immutable image, current and previous source SHA, migration result, verification result, deployment time, and pre-migration backup path.

## Manual local-on-VPS invocation

The deployment script reads registry username and password as the first two lines on standard input. This avoids command-line credential arguments:

```bash
{
  printf '%s\n' "$REGISTRY_USERNAME"
  printf '%s\n' "$REGISTRY_PASSWORD"
} | bash deploy/vps/deploy.sh \
  'docker.io/example/kaori@sha256:<64-hex-digest>' \
  '<40-hex-source-sha>'
```

Do not enable shell tracing around credentials.

## Verification

Run independently at any time:

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production bash deploy/vps/verify.sh
```

Verification requires PostgreSQL and Redis to be healthy, all canonical KAORI runtime services to be running, exactly one Beat container, and loopback readiness to return success.

## Backup and restore

Create an explicit backup:

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production bash deploy/vps/backup.sh
```

The command writes a PostgreSQL custom-format dump and SHA256 sidecar under `/var/lib/kaori/backups` by default.

Restore is never automatic. Select the reviewed recovery point explicitly:

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production \
  bash deploy/vps/restore.sh /var/lib/kaori/backups/kaori-postgres-<timestamp>.dump
```

A restore is destructive to the current logical database state and must be coordinated with application shutdown/recovery procedure.

## Rollback

`rollback.sh` uses the recorded `previous-image` and `previous-source-sha` and then re-enters the same governed `deploy.sh` path. Supply fresh registry credentials through standard input exactly as for deployment.

```bash
{
  printf '%s\n' "$REGISTRY_USERNAME"
  printf '%s\n' "$REGISTRY_PASSWORD"
} | bash deploy/vps/rollback.sh
```

An image rollback does **not** reverse database migrations. If the rejected release changed the schema incompatibly, restore the matching reviewed pre-migration backup after intentionally selecting that recovery point.

## Handoff to public ingress

Issue #49 is complete only after an admitted immutable image is actually pulled and the full runtime is healthy on loopback. Issue #50 then owns DNS, Nginx, TLS/ACME renewal, default-host rejection, public port minimization, SSH/firewall hardening, and external DAST until `https://kaori.cloud` is accepted.

No `main` promotion or stable release is authorized by this deployment surface. That remains governed by explicit UAT acceptance and Issue #51.
