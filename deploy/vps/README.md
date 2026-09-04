# KAORI VPS deployment

`deploy/vps/` owns KAORI application deployment to the single UAT/production-like VPS. It is intentionally separate from `ops/github-runner/`, which owns only GitHub self-hosted runner host lifecycle.

`compose.production.yml` remains the canonical KAORI application graph. `deploy/vps/compose.vps.yml` adds private PostgreSQL and Redis state services plus deployment, verification, backup, restore, rollback, and host-preparation operator surfaces.

## Security and ownership model

- Use a dedicated non-root deploy user. Docker access is root-equivalent privilege and must be granted deliberately.
- SSH is key-only. Generate the passphrase-protected RSA keypair on the operator laptop. Only the public `.pub` key is copied to the VPS; the private key never belongs on the deployment host.
- The UAT workflow receives the encrypted private key and passphrase from GitHub Environment secrets and uses the reviewed `KAORI_VPS_KNOWN_HOSTS` record. `StrictHostKeyChecking=yes` is mandatory.
- Registry credentials come from GitHub Secrets. The remote deploy uses `docker login --password-stdin` with an ephemeral `DOCKER_CONFIG` directory that is deleted after the rollout.
- The real application environment exists only on the VPS at `/etc/kaori/.env.production`, mode `600`. Never commit it or upload it as an Actions artifact.
- `/etc/kaori/.env.production` is **long-lived operator configuration**. Ordinary application releases do not rewrite it and do not require manual image/version edits.
- Application `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` are governed release identity supplied ephemerally by the deployment transaction and recorded under `/var/lib/kaori/deploy-state` after success.
- PostgreSQL and Redis have no host `ports` mapping. KAORI web stays on `127.0.0.1:5000`; public ingress belongs to `deploy/nginx/` and Issue #50.
- KAORI, PostgreSQL, and Redis deployment images must use immutable digest authority. Do not use `latest` or mutable dependency tags for UAT/production deployment.

## Temporary UAT co-location with the GitHub runner

During UAT, the GitHub self-hosted runner and the KAORI deployment target may share the **same physical VPS** because of the current infrastructure constraint. Physical co-location does not merge their operational domains or Unix identities.

- The runner remains `github-runner` under `/opt/actions-runner` and is owned only by `ops/github-runner/`.
- KAORI deployment remains `kaori-deploy` under `/opt/kaori` and is owned only by `deploy/vps/`.
- `/etc/kaori/.env.production` and `/var/lib/kaori/` remain application deployment/runtime state and must not be copied into the runner workspace.
- `deploy/vps/bootstrap-host.sh` rejects `github-runner` as the deploy user and does not modify runner registration, runner service files, or `/opt/actions-runner`.
- **SSH remains the deployment boundary** even when the self-hosted runner and target currently resolve to the same host. Configure `KAORI_VPS_HOST` with the reviewed VPS hostname/IP and retain pinned `KAORI_VPS_KNOWN_HOSTS`; do not add a localhost/direct-execution bypass.
- Docker access for both identities is root-equivalent privilege. This co-location is an accepted **temporary UAT** constraint, not the desired long-term production isolation posture.

When infrastructure capacity permits, move the GitHub runner to a separate host or runner pool. The governed SSH deployment interface should remain unchanged when that happens.

## One-time VPS preparation

`deploy/vps/bootstrap-host.sh` prepares the application-deployment host only. It creates the deploy user, installs/verifies Docker and the Compose plugin, installs the operator-provided RSA public key, prepares the canonical release/state/backup paths, and initializes the server-side environment file if it does not already exist.

It does **not** generate an SSH keypair, change `sshd_config`, configure the firewall, install Nginx/Certbot, change DNS, or expose KAORI publicly. Those host-ingress hardening responsibilities remain Issue #50.

### 1. Generate the deployment RSA keypair on the laptop

Run this on the operator laptop, not on the VPS:

```bash
ssh-keygen -t rsa -b 4096 -o -a 100 \
  -f ~/.ssh/kaori-uat-deploy \
  -C 'kaori-uat-deploy'
```

Use a strong passphrase when prompted.

This produces:

- `~/.ssh/kaori-uat-deploy` — **private key**. Keep it on the laptop and later copy its contents only to the GitHub Environment secret `KAORI_VPS_SSH_PRIVATE_KEY`.
- `~/.ssh/kaori-uat-deploy.pub` — public key. This is the only key file that may be copied to the VPS for bootstrap.

The private-key passphrase is stored separately in `KAORI_VPS_SSH_PASSPHRASE`. Never copy the private key or its passphrase into `/opt/kaori`, `/etc/kaori`, a release directory, or an Actions artifact.

### 2. Copy bootstrap material and the public key to the VPS

Use the initial trusted administrative access supplied for the VPS. For example, from a reviewed KAORI checkout on the laptop:

```bash
ssh root@<vps-host> 'install -d -m 0700 /root/kaori-bootstrap'

scp \
  ~/.ssh/kaori-uat-deploy.pub \
  deploy/vps/bootstrap-host.sh \
  .env.production.example \
  root@<vps-host>:/root/kaori-bootstrap/
```

Only non-secret repository bootstrap material and the public `.pub` key are copied here.

### 3. Run the bootstrap on the VPS

On the VPS:

```bash
sudo bash /root/kaori-bootstrap/bootstrap-host.sh \
  --ssh-public-key-file /root/kaori-bootstrap/kaori-uat-deploy.pub \
  --env-template /root/kaori-bootstrap/.env.production.example
```

Defaults:

- deploy user: `kaori-deploy`;
- deploy root: `/opt/kaori`;
- environment: `/etc/kaori/.env.production`;
- deployment state: `/var/lib/kaori/deploy-state`;
- backups: `/var/lib/kaori/backups`;
- SSH port metadata: `22`.

Override only when the real host requires it:

```bash
sudo bash /root/kaori-bootstrap/bootstrap-host.sh \
  --ssh-public-key-file /root/kaori-bootstrap/kaori-uat-deploy.pub \
  --env-template /root/kaori-bootstrap/.env.production.example \
  --deploy-user kaori-deploy \
  --deploy-root /opt/kaori \
  --ssh-port 22
```

The script is idempotent. If `/etc/kaori/.env.production` already exists, its content is preserved and only the governed ownership/mode is reasserted. The dedicated deploy user's `authorized_keys` is replaced with the one operator-supplied public key, which makes deliberate key rotation deterministic.

Docker group membership is intentionally granted to the deploy user because the current deployment surface uses Docker Compose directly. Treat that membership as root-equivalent privilege and keep the account dedicated to KAORI deployment.

If `/opt/actions-runner` already exists on this VPS, the bootstrap reports the co-location and preserves that path. It never uses the `github-runner` account for KAORI deployment.

### 4. Verify the new deploy identity from the laptop

After bootstrap completes:

```bash
ssh -i ~/.ssh/kaori-uat-deploy kaori-deploy@<vps-host>
```

Then verify the runtime prerequisites:

```bash
docker info
docker compose version
stat -c '%a %U %G %n' /etc/kaori/.env.production
```

The environment file must report mode `600` and the deploy-user ownership expected by the deployment scripts.

### 5. Pin the VPS host key before GitHub deployment

Do not learn-and-trust the SSH host key inside the deployment workflow. Collect a candidate host-key record from a trusted operator machine, then verify its fingerprint independently through the VPS/provider console or another trusted channel before storing it in GitHub:

```bash
ssh-keyscan -p 22 <vps-host> > kaori-vps.known_hosts.candidate
ssh-keygen -lf kaori-vps.known_hosts.candidate
```

Only after the fingerprint is independently verified should the exact known-hosts record become the `KAORI_VPS_KNOWN_HOSTS` GitHub Environment secret.

### 6. Complete the server-side production environment once

Edit the real host file after bootstrap:

```bash
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

Do **not** add or update `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, or `APP_BUILD_DATE` for ordinary releases. Those four values are resolved from governed release evidence and the immutable image by `deploy.sh`. If a pre-contract host file still contains historical values for those keys, they are not release authority because Compose explicitly overrides them with deployment-supplied values; remove the stale entries during a reviewed maintenance edit to keep the host file unambiguous.

PostgreSQL/Redis image digests are different: they are long-lived state-dependency configuration. Change `KAORI_POSTGRES_IMAGE` or `KAORI_REDIS_IMAGE` only as a deliberate infrastructure/database upgrade, not as part of every KAORI application release.

## GitHub Environment configuration

Use the GitHub Environment `uat` for deployment credentials and protection policy.

Secrets:

- `KAORI_VPS_SSH_PRIVATE_KEY` — contents of the private `~/.ssh/kaori-uat-deploy` file retained off-host;
- `KAORI_VPS_SSH_PASSPHRASE` — the private-key passphrase stored separately;
- `KAORI_VPS_KNOWN_HOSTS` — independently verified host-key record;
- `KAORI_DOCKER_REGISTRY_USERNAME`;
- `KAORI_DOCKER_REGISTRY_PASSWORD`.

Variables:

- `KAORI_VPS_HOST`;
- `KAORI_VPS_USER` (default bootstrap value `kaori-deploy`);
- `KAORI_VPS_PORT` (normally `22`);
- `KAORI_VPS_DEPLOY_ROOT` (optional; defaults to `/opt/kaori`).

`KAORI_VPS_KNOWN_HOSTS` must contain the reviewed host-key entry for the exact VPS endpoint. Deployment must never learn-and-trust a host key automatically.

When the runner is co-located, `KAORI_VPS_HOST` still identifies the reviewed VPS endpoint. Do not replace the SSH trust boundary with `localhost` merely because the current runner happens to run on the target host.

## Intentional RC deployment authority

`.github/workflows/deploy-uat-vps.yml` supports two governed request paths.

For the initial/current bootstrap path, use the dedicated `kaori/uat-request` branch. GitHub only exposes `workflow_dispatch` when the workflow file already exists on the repository default branch, while KAORI deliberately requires UAT before staging is promoted to `main`. Therefore the first governed UAT request is branch-driven rather than a manual Actions button.

The required order is:

1. merge reviewed work to `kaori/staging`;
2. wait for exact Full Admission (`quality.yml`) PASS on that staging SHA;
3. cut the fresh intentional RC for that exact SHA;
4. move `kaori/uat-request` to that same exact staging SHA;
5. let `KAORI UAT VPS Deploy` auto-resolve the one intentional prerelease targeting that SHA and continue through the normal evidence/SSH deployment transaction.

Do not move `kaori/uat-request` before the fresh RC exists. A stale request SHA, missing RC, or ambiguous RC evidence fails closed before SSH.

After `deploy-uat-vps.yml` has reached the default branch through normal promotion, the manual path remains available: dispatch `KAORI UAT VPS Deploy` against `kaori/staging` with the intentional RC `candidate_tag`. Manual dispatch does not weaken the same exact-SHA/evidence checks.

Before any SSH connection is opened, either path verifies:

1. the request SHA is the current `kaori/staging` SHA;
2. the candidate is a GitHub prerelease targeting that exact SHA;
3. its tag SHA is the current `kaori/staging` SHA;
4. exact `quality.yml` Full Admission succeeded for that SHA;
5. the corresponding successful `publish-staging-image.yml` run exists;
6. the `staging-image-<sha>` artifact exists and is unexpired;
7. `staging-image.env` agrees on `KAORI_CANDIDATE_TAG`, `KAORI_SOURCE_SHA`, and immutable `KAORI_IMAGE_REF`.

The workflow passes three release-authority values to the remote transaction: the immutable application image digest, the exact accepted source SHA, and the exact candidate version. `deploy.sh` derives `APP_BUILD_DATE` from the pulled immutable image metadata. No ordinary application release edits `/etc/kaori/.env.production`.

Free-form image/SHA deployment is not an authorized UAT path. After a staging source change, cut a fresh intentional RC from that newly admitted exact staging SHA instead of deploying an older historical RC.

## Deployment lifecycle

The remote `deploy.sh` performs, in order:

1. validate the digest-qualified application image, exact source SHA, governed release version, host prerequisites, and persistent env-file permissions;
2. use ephemeral registry authentication and pull the exact immutable application image;
3. verify the image OCI revision equals the requested source SHA and derive the image creation timestamp;
4. export `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` only for the deployment transaction, then validate Compose;
5. pull and start immutable PostgreSQL/Redis dependencies without public ports;
6. wait for both state services to become healthy;
7. detect an existing application schema and require a successful pre-migration PostgreSQL backup;
8. run KAORI environment validation with deployment-supplied release identity;
9. run the one-shot database migration;
10. replace the application graph using the already-pulled immutable image with `--pull never`;
11. verify runtime services, worker queue introspection, single Beat, exact image identity, private state ports, and loopback readiness;
12. record current/previous immutable image, source SHA, release version, build timestamp, migration result, backup evidence, and verification result in `/var/lib/kaori/deploy-state`.

## Verification

After at least one successful governed deployment, verification reloads the recorded current release identity automatically; it does not need release fields in `/etc/kaori/.env.production`:

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production \
  bash deploy/vps/verify.sh --restart-check
```

During an active deployment, `deploy.sh` supplies the expected immutable image directly to the verifier.

## Backup and restore

Create a PostgreSQL custom-format backup with checksum. The backup command reloads current release identity from deployment state when it is not already running inside a deploy transaction:

```bash
KAORI_ENV_FILE=/etc/kaori/.env.production bash deploy/vps/backup.sh
```

Restore is fail-closed: the dump must be under `/var/lib/kaori/backups`, have its SHA256 sidecar, and application services are stopped before `pg_restore --exit-on-error` runs. Current release identity is likewise recovered from deployment state for Compose parsing.

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

The rollback surface restores the reviewed database recovery point, then redeploys the recorded previous immutable image, previous source SHA, and previous release version through the same governed `deploy.sh` path. The build timestamp is re-derived from that immutable image.

## Public ingress boundary

Issue #49 establishes the private VPS runtime and governed UAT deployment surface. Issue #50 owns DNS, Nginx reverse proxy, TLS/ACME renewal, default-host rejection, public port minimization, firewall/SSH hardening, and external HTTPS/DAST acceptance.

No `main` promotion or stable release is authorized by Issue #49. Stable promotion remains Issue #51 and requires explicit UAT acceptance of the exact staging SHA and immutable application image digest; promotion must reuse the accepted digest without rebuilding the image.
