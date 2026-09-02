# KAORI VPS Compose Deployment Design

## Goal
Provide a governed, reproducible UAT deployment path for the complete KAORI production service graph on one VPS using an immutable Docker Registry digest, private persistent PostgreSQL/Redis dependencies, server-side configuration, controlled migration, rollback evidence, and fail-closed SSH/registry handling.

## Operational boundaries
VPS deployment is owned by `deploy/vps/`. GitHub self-hosted runner lifecycle remains owned independently by `ops/github-runner/`. Public ingress remains owned by `deploy/nginx/` and Issue #50.

The production application graph remains canonical in `compose.production.yml`. The VPS layer adds only host-specific state dependencies and deployment tooling. Application runtime code does not depend on `deploy/`.

## Runtime topology
`compose.production.yml` continues to define web, inventory worker, maintenance worker, integration runtime worker, integration validation worker, analytics worker, reports worker, forecasting worker, resolver execution worker, resolver maintenance worker, and exactly one Celery Beat service. It accepts a configurable `KAORI_ENV_FILE`, defaulting to `.env.production` for existing workflows.

`deploy/vps/compose.vps.yml` adds PostgreSQL 16 and Redis 7 on the existing private `kaori_production` network. Neither state service publishes a host port. Both use named volumes, restart policies, authentication, and health checks.

The VPS production environment is stored at `/etc/kaori/.env.production`. It is created from `.env.production.example` by the operator, contains real secrets only on the server, is readable by the dedicated deploy user, and uses mode `0600`. Ordinary deployments preserve this file and inject only the requested immutable `KAORI_IMAGE` rollout identity.

## Deployment transaction
A deployment accepts only an image reference containing `@sha256:<64 lowercase hex characters>`. Mutable-only tags and `latest` are rejected.

The deployment script validates prerequisites and environment permissions, creates an ephemeral `DOCKER_CONFIG`, reads registry username/password from standard input, authenticates with `docker login --password-stdin`, and removes the temporary Docker credential directory through an exit trap.

The sequence is:

1. Validate immutable image and server environment.
2. Pull the exact image digest.
3. Start PostgreSQL and Redis only.
4. Wait for dependency health.
5. Run the production environment validator.
6. If an existing database schema is present, create a timestamped pre-migration PostgreSQL backup.
7. Run the one-shot database migration.
8. Start the complete application graph.
9. Verify all expected services and loopback web readiness.
10. Record exact source SHA, current image digest, previous image digest, migration result, deployment timestamp, and verification result under the server deployment-state directory.

A failed validation, dependency health check, backup, migration, or readiness check fails the deployment closed. Automatic destructive database restore is not performed.

## Backup, restore, and rollback
`backup.sh` writes PostgreSQL custom-format dumps to a restricted server backup directory and records a SHA256 checksum. `restore.sh` requires an explicit backup file, verifies the checksum when available, and restores through PostgreSQL tooling after an operator has intentionally selected the recovery point.

`rollback.sh` reads the recorded previous immutable image and invokes the same governed deploy path. Image rollback is explicitly distinct from database rollback. If the failed rollout included an incompatible migration, the operator must pair image rollback with the reviewed database restore procedure.

## Remote delivery workflow
`.github/workflows/deploy-uat-vps.yml` is manual-only (`workflow_dispatch`). It is allowed only from the admitted `kaori/staging` lineage and requires a digest-qualified image input plus its source SHA.

SSH uses:
- `KAORI_VPS_SSH_PRIVATE_KEY` secret;
- `KAORI_VPS_SSH_PASSPHRASE` secret;
- `KAORI_VPS_SSH_KNOWN_HOSTS` secret containing the pinned host key;
- repository/environment variables for host, user, and port.

The encrypted RSA key is loaded into an ephemeral `ssh-agent` with an ephemeral `SSH_ASKPASS` helper. The workflow uses `StrictHostKeyChecking=yes` and the supplied known-hosts file. `StrictHostKeyChecking=no` is prohibited.

The workflow copies only the deployment bundle needed by the VPS, then invokes the remote deploy script. Registry credentials are consumed from GitHub Secrets and streamed to the remote script over the encrypted SSH session; they are not persisted in repository content or a long-lived server Docker config.

## Single active VPS slot
The current environment has one physical VPS and one active KAORI Compose project. A newer staging/RC deployment replaces the active image. Parallel staging and production stacks are intentionally out of scope. Current and previous immutable image identities are always recorded so the previous candidate remains a known rollback target.

## Ingress dependency
Issue #49 proves `127.0.0.1:5000/health/ready` and full internal runtime health. Issue #50 subsequently owns Nginx, TLS/ACME, DNS, unknown-host rejection, public port minimization, SSH/firewall hardening, and external DAST. No public PostgreSQL, Redis, Docker API, or direct KAORI application port is introduced by this design.

## Validation
Work-branch validation is the path-aware Developer Check. The contract under `tests/contracts/platform_operations/test_vps_deployment_surface_contract.py` locks the deployment boundary, immutable image policy, private state services, server-side env path, ephemeral registry authentication, backup/restore/rollback ownership, loopback readiness, and pinned SSH host verification.

After merge to `kaori/staging`, comprehensive KAORI CI is authoritative. Actual VPS UAT remains separate evidence and does not authorize `main` promotion without explicit maintainer acceptance under Issue #51.
