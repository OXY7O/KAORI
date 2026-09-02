# KAORI VPS deployment

`deploy/vps/` owns KAORI application deployment to the single UAT/production-like VPS. It is intentionally separate from `ops/github-runner/`, which owns only GitHub self-hosted runner host lifecycle.

`compose.production.yml` remains the canonical KAORI application graph. `deploy/vps/compose.vps.yml` adds private PostgreSQL and Redis state services plus deployment, verification, backup, restore, and rollback operator surfaces.

## Security and ownership model

- Use a dedicated non-root deploy user. Docker access is root-equivalent privilege and must be granted deliberately.
- SSH is key-only. The UAT workflow uses a passphrase-protected RSA key from GitHub Secrets and the reviewed `KAORI_VPS_KNOWN_HOSTS` record. `StrictHostKeyChecking=yes` is mandatory.
- Registry credentials come from GitHub Secrets. The remote deploy uses `docker login --password-stdin` with an ephemeral `DOCKER_CONFIG` directory that is deleted after the rollout.
- The real application environment exists only on the VPS at `/etc/kaori/.env.production`, mode `600`. Never commit it or upload it as an Actions artifact.
- PostgreSQL and Redis have no host `ports` mapping. KAORI web stays on `127.0.0.1:5000`; public ingress belongs to `deploy/nginx/` and Issue #50.
- KAORI, PostgreSQL, and Redis deployment images must use immutable digest authority. Do not use `latest` or mutable dependency tags for UAT/production deployment.

## One-time VPS preparation

Install Docker Engine and the Docker Compose plugin through the approved host-management process. Prepare the non-root deploy user and directories:

```bash
sudo install -d -m 0755 /etc/kaori
sudo install -d -m 0700 -o <deploy-user> -g <deploy-user> /var/lib/kaori/deploy-state
sudo install -d -m 0700 -o <deploy-user> -g <deploy-user> /var/lib/kaori/backups
sudo install -d -m 0755 -o <deploy-user> -g <deploy-user> /opt/kaori/releases
```

Copy `.env.production.example` to the server only, then populate real values manually or through the approved secret-management process:

```bash
sudo install -m 0600 -o <deploy-user> -g <deploy-user> .env.production.example /etc/kaori/.env.production
sudoedit /etc/kaori/.env.production
```

For the VPS topology, ensure `/etc/kaori/.env.production` includes at least:

```text
KAORI_POSTGRES_IMAGE=postgres@sha256:<reviewed-immutable-digest>
KAORI_REDIS_IMAGE=redis@sha256:<reviewed-immutable-digest>
POSTGRES_DB=kaori
POSTGRES_USER=kaori
POSTGRES_PASSWORD=<strong-random-url-safe-value>
REDIS_PASSWORD=<strong-random-url-safe-value>
DATABASE_URL=postgresql://kaori:<postgres-password>@postgres:5432/kaori
REDIS_URL=redis://:<redis-password>@redis:6379/0
CELERY_BROKER_URL=redis://:<redis-password>@redis:6379/1
RATELIMIT_STORAGE_URI=redis://:<redis-password>@redis:6379/2
CELERY_RESULT_BACKEND=redis://:<redis-password>@redis:6379/3
KAORI_PUBLIC_BASE_URL=https://kaori.cloud
TRUSTED_HOSTS=kaori.cloud,127.0.0.1,localhost
KAORI_BIND_ADDRESS=127.0.0.1
KAORI_PORT=5000
```

Use URL-safe passwords or URL-encode credentials embedded in connection URLs. Populate the remaining application, S3/MinIO, authentication, integration, and worker settings from `.env.production.example`. Remove `ADMIN_PASSWORD` after first administrator bootstrap.

## GitHub Environment configuration

Use the GitHub Environment `uat` for deployment credentials and protection policy.

Secrets:

- `KAORI_VPS_SSH_PRIVATE_KEY`
- `KAORI_VPS_SSH_PASSPHRASE`
- `KAORI_VPS_KNOWN_HOSTS`
- `KAORI_DOCKER_REGISTRY_USERNAME`
- `KAORI_DOCKER_REGISTRY_PASSWORD`

Variables:

- `KAORI_VPS_HOST`
- `KAORI_VPS_USER`
- `KAORI_VPS_PORT` (normally `22`)
- `KAORI_VPS_DEPLOY_ROOT` (optional; defaults to `/opt/kaori`)

`KAORI_VPS_KNOWN_HOSTS` must contain the reviewed host-key entry for the exact VPS endpoint. Deployment must never learn-and-trust a host key automatically.

## Intentional RC deployment authority

`.github/workflows/deploy-uat-vps.yml` is the normal remote entry point. Dispatch it from `kaori/staging` with one input only: the intentional RC `candidate_tag` previously published by `.github/workflows/publish-staging-image.yml`.

Before any SSH connection is opened, the workflow verifies:

1. the requested tag is a GitHub prerelease;
2. its tag SHA is the current `kaori/staging` SHA;
3. exact `quality.yml` Full Admission succeeded for that SHA;
4. the corresponding successful `publish-staging-image.yml` run exists;
5. the `staging-image-<sha>` artifact exists and is unexpired;
6. `staging-image.env` agrees on `KAORI_CANDIDATE_TAG`, `KAORI_SOURCE_SHA`, and immutable `KAORI_IMAGE_REF`.

Free-form image/SHA deployment is not an authorized UAT path.

## Deployment lifecycle

The remote `deploy.sh` performs, in order:

1. validate the digest-qualified application image and its OCI source revision;
2. validate `/etc/kaori/.env.production` and Compose configuration;
3. use ephemeral registry authentication;
4. pull and start immutable PostgreSQL/Redis dependencies without public ports;
5. wait for both state services to become healthy;
6. detect an existing application schema and require a successful pre-migration PostgreSQL backup;
7. run KAORI environment validation;
8. run the one-shot database migration;
9. replace the application graph using the already-pulled immutable image with `--pull never`;
10. verify runtime services, worker queue introspection, single Beat, exact image identity, private state ports, and loopback readiness;
11. record deployment and recovery evidence in `/var/lib/kaori/deploy-state`.

## Verification

Run independently:

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production \
  KAORI_EXPECTED_IMAGE='registry.example/kaori@sha256:<digest>' \
  bash deploy/vps/verify.sh --restart-check
```

## Backup and restore

Create a PostgreSQL custom-format backup with checksum:

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production bash deploy/vps/backup.sh
```

Restore is fail-closed: the dump must be under `/var/lib/kaori/backups`, have its SHA256 sidecar, and application services are stopped before `pg_restore --exit-on-error` runs.

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production \
  bash deploy/vps/restore.sh /var/lib/kaori/backups/kaori-postgres-<timestamp>.dump
```

## Rollback

KAORI refuses image-only rollback because a newer schema may be incompatible with the previous image. A rollback must explicitly restore the recorded pre-migration backup first:

```bash
{
  printf '%s\n' "$REGISTRY_USERNAME"
  printf '%s\n' "$REGISTRY_PASSWORD"
} | bash deploy/vps/rollback.sh --restore-backup
```

The rollback surface restores the reviewed database recovery point, then redeploys the recorded previous immutable image/source through the same governed `deploy.sh` path.

## Public ingress boundary

Issue #49 establishes the private VPS runtime and governed UAT deployment surface. Issue #50 owns DNS, Nginx reverse proxy, TLS/ACME renewal, default-host rejection, public port minimization, firewall/SSH hardening, and external HTTPS/DAST acceptance.

No `main` promotion or stable release is authorized here. Stable promotion remains Issue #51 after explicit UAT review of the exact RC digest.
