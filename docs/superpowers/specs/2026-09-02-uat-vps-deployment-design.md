# KAORI UAT VPS Deployment Design

## Purpose

Provide a governed, repeatable UAT deployment path for the full KAORI production Compose graph on one VPS. Deployment consumes only an intentionally published immutable Release Candidate, preserves server-side secrets, performs data-safety gates before migration, and exposes KAORI only through the existing loopback web binding. Public Nginx/TLS acceptance remains owned by #50.

## Authority and Boundaries

- Source integration authority is `kaori/staging` after comprehensive KAORI CI Full Admission.
- Artifact authority is an intentional KAORI Release Candidate produced by `.github/workflows/publish-staging-image.yml`.
- VPS deployment tooling is owned by `deploy/vps/` and is separate from `ops/github-runner/`.
- `compose.production.yml` remains the canonical KAORI application-service graph.
- `deploy/vps/compose.vps.yml` adds only VPS-local PostgreSQL and Redis dependencies and their persistent volumes.
- Real deployment secrets remain server-side in `/etc/kaori/.env.production` or in GitHub Environment secrets. They are never committed or uploaded as deployment artifacts.
- Public Nginx, ACME/TLS, firewall hardening, and external DAST are implemented under #50 after #49 proves loopback runtime readiness.
- Stable/main promotion is out of scope until explicit UAT acceptance under #51.

## Deployment Model

The current infrastructure constraint is one physical VPS and one active KAORI stack. A new UAT candidate replaces the currently active application image. Parallel staging and production stacks are intentionally not created.

Every deployment records:

- exact accepted source SHA;
- RC tag;
- current immutable application image reference (`registry/image@sha256:...`);
- previous immutable image reference;
- database backup path when an existing database was detected;
- migration result;
- readiness/verification result;
- deployment timestamp.

The application image is always deployed by digest. Mutable tags are metadata only and are not rollout authority.

## Repository Layout

```text
deploy/
├── nginx/
│   └── kaori.conf.example
└── vps/
    ├── README.md
    ├── compose.vps.yml
    ├── deploy.sh
    ├── verify.sh
    ├── backup.sh
    ├── restore.sh
    └── rollback.sh

.github/workflows/
└── deploy-uat-vps.yml
```

`deploy/vps/` is operational deployment tooling, not application runtime content. The production Dockerfile allowlist established by #99 must continue excluding `deploy/`.

## Environment Contract

`.env.production.example` stays a template. The real file is created once on the VPS at:

```text
/etc/kaori/.env.production
```

Recommended ownership/mode is a dedicated deploy owner/group with mode `0640` or stricter. The tooling fails closed if the file is missing or world-accessible/writable.

`compose.production.yml` will read its service `env_file` from:

```yaml
env_file:
  - ${KAORI_ENV_FILE:-.env.production}
```

The default preserves the existing local/operator contract. VPS deployment sets `KAORI_ENV_FILE=/etc/kaori/.env.production` and invokes Compose with `--env-file` against the same file. The rollout exports `KAORI_IMAGE` from the verified immutable RC evidence, so a stale `KAORI_IMAGE` line in the host file cannot override rollout authority.

For the single-VPS dependency overlay, the host file contains production values for PostgreSQL and Redis. Application URLs use the private Compose service names `postgres` and `redis`; neither service publishes a host port.

Dependency images should also be configured as immutable digest references through `KAORI_POSTGRES_IMAGE` and `KAORI_REDIS_IMAGE`. This avoids silently changing database/cache binaries during an application rollout.

## Compose Topology

`compose.production.yml` continues to define:

- `validate`;
- `migrate`;
- `web`;
- inventory worker;
- maintenance worker;
- integration runtime worker;
- integration validation worker;
- analytics worker;
- reports worker;
- forecasting worker;
- resolver execution worker;
- resolver maintenance worker;
- exactly one Beat service.

`deploy/vps/compose.vps.yml` adds:

- `postgres` with authentication, healthcheck, restart policy, and named persistent volume;
- `redis` with authentication, append-only persistence, healthcheck, restart policy, and named persistent volume.

Both dependencies attach only to the existing private `kaori_production` network and expose no `ports` entries.

The deploy sequence starts PostgreSQL and Redis first and waits for health before any application validation or migration. One-shot `validate` and `migrate` are invoked explicitly and are never accidentally started as long-running services.

## SSH Trust Boundary

The GitHub deployment workflow uses a dedicated encrypted RSA private key. The following values are governed outside repository content:

Environment secrets:

- `KAORI_VPS_SSH_PRIVATE_KEY`;
- `KAORI_VPS_SSH_PASSPHRASE`;
- `KAORI_VPS_KNOWN_HOSTS`;
- `KAORI_DOCKER_REGISTRY_USERNAME`;
- `KAORI_DOCKER_REGISTRY_PASSWORD`.

Environment/repository variables:

- `KAORI_VPS_HOST`;
- `KAORI_VPS_USER`;
- `KAORI_VPS_PORT`;
- existing `KAORI_DOCKER_REGISTRY_HOST`;
- existing `KAORI_DOCKER_REGISTRY_IMAGE`.

The private key is written only into `RUNNER_TEMP`, mode `0600`, loaded into `ssh-agent` using an `SSH_ASKPASS` helper that reads the passphrase from an environment variable, and deleted in an `always()` cleanup step. The known-hosts file is supplied from governed input; `StrictHostKeyChecking=yes` is mandatory and `StrictHostKeyChecking=no` is prohibited.

Normal deployment uses the operator-prepared non-root deploy user. Docker access is explicitly treated as root-equivalent privilege.

## RC Evidence Resolution

The remote deploy workflow is manual and targets the GitHub Environment `uat`. Its operator input is the RC tag, not a free-form image digest.

Before opening SSH, the workflow:

1. validates the requested tag syntax;
2. resolves the GitHub prerelease and requires `prerelease=true`;
3. resolves the tag target to an exact 40-character source SHA;
4. requires successful `quality.yml` authority for that exact SHA;
5. locates the successful `publish-staging-image.yml` run for the source;
6. downloads the `staging-image-<source_sha>` evidence artifact;
7. validates that artifact source SHA and RC tag match the requested release;
8. validates that `KAORI_IMAGE_REF` is rooted at the configured registry image and ends in `@sha256:<64 hex>`.

Only that verified `KAORI_IMAGE_REF` is allowed into the remote deploy step.

## Registry Authentication

Registry credentials are not stored permanently on the VPS.

For each deployment the workflow opens the pinned SSH session and:

1. creates a temporary remote `DOCKER_CONFIG` directory;
2. pipes the registry password through standard input to `docker login --password-stdin`;
3. pulls the verified immutable application image;
4. runs deployment using the same temporary Docker config;
5. logs out and removes the temporary directory through an EXIT trap.

The registry password is never put in a command-line argument or committed server file.

## Remote Release Assets

The workflow transfers only the deployment contract required by the VPS:

- `compose.production.yml`;
- `deploy/vps/`.

They are extracted into a source-addressed release directory under `/opt/kaori/releases/<source_sha>/`. This gives each deployment an auditable copy of the exact operational assets without requiring a Git checkout or GitHub credential on the VPS.

Operational state and backups are outside the release directory so replacing release assets cannot delete them:

- state: `/opt/kaori/state/`;
- backups: `/opt/kaori/backups/postgres/`.

The deploy user must own/write these paths before UAT deployment.

## Data Safety and Migration

After PostgreSQL becomes healthy, deployment checks whether the database already contains non-system tables.

- Empty/new database: no pre-migration backup is required.
- Existing database: `backup.sh` must successfully create a PostgreSQL custom-format dump before migration proceeds.

`validate` then runs against the exact candidate environment. Only after validation passes does `migrate` run. Any failure stops the rollout before long-running application services are replaced.

The backup path is included in deployment state. Image rollback is never represented as database rollback.

## Verification

`verify.sh` is independently callable and fail-closed. It validates:

- PostgreSQL and Redis containers are running and healthy;
- no PostgreSQL or Redis host ports are published;
- web is running and Docker health is healthy;
- host loopback readiness responds through the published `127.0.0.1:<port>` mapping;
- all canonical KAORI worker services are running;
- Celery active-queue evidence contains every configured canonical queue;
- exactly one Beat container is running;
- every long-running KAORI application service uses the exact expected immutable image digest.

An explicit `--restart-check` mode performs a controlled persistence probe for the KAORI instance volume and dependency containers. This is UAT evidence and is not run on every normal deployment.

## Rollback and Restore

`rollback.sh` reads the recorded previous immutable image reference. If the deployment state records a pre-migration database backup, rollback refuses an image-only rollback unless the operator explicitly provides the recorded backup for restore. This prevents representing incompatible schema rollback as safe.

`restore.sh` is an explicit destructive operation. It stops KAORI application services, verifies the selected backup is inside the governed backup directory, recreates the application database through the PostgreSQL service, restores the custom-format dump, and leaves final application startup to the rollback/deploy flow.

## Failure Behavior

Deployment fails closed on:

- missing/malformed RC evidence;
- source SHA without successful staging quality authority;
- non-immutable application image reference;
- missing SSH key/passphrase/known-hosts trust material;
- host-key mismatch;
- missing/rejected registry credentials;
- inaccessible `/etc/kaori/.env.production`;
- insecure environment-file permissions;
- mutable/missing PostgreSQL or Redis image authority;
- unhealthy PostgreSQL or Redis;
- failed backup on an existing database;
- failed production environment validation;
- failed migration;
- failed web/worker/Beat verification.

No step silently falls back to a tag, local build, development database, or unauthenticated Redis.

## Testing and Admission

Work-branch TDD contracts lock:

- the `deploy/vps/` ownership boundary;
- server-side environment-file support;
- private PostgreSQL/Redis Compose topology and persistence;
- immutable RC-only workflow authority;
- pinned SSH host verification and encrypted-key handling;
- ephemeral `docker login --password-stdin` behavior;
- backup-before-migration ordering;
- explicit validate/migrate before long-running services;
- independent verification/rollback/restore surfaces;
- no deployment tooling in the production image.

The work branch receives only Developer Check. After exact-candidate integration into `kaori/staging`, comprehensive KAORI CI remains the staging authority. Actual SSH deployment is held until the required UAT secrets/variables and a fresh intentional RC exist, and until human UAT review is authorized.