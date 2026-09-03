# KAORI VPS Compose Deployment Design

## Goal
Provide a governed, reproducible UAT deployment path for the complete KAORI production service graph on one VPS using an immutable Docker Registry digest, private persistent PostgreSQL/Redis dependencies, persistent server-side configuration, ephemeral release identity, controlled migration, rollback evidence, and fail-closed SSH/registry handling.

## Operational boundaries
VPS deployment is owned by `deploy/vps/`. GitHub self-hosted runner lifecycle remains owned independently by `ops/github-runner/`. Public ingress remains owned by `deploy/nginx/` and Issue #50.

The production application graph remains canonical in `compose.production.yml`. The VPS layer adds only host-specific state dependencies and deployment tooling. Application runtime code does not depend on `deploy/`.

## Runtime topology
`compose.production.yml` continues to define web, inventory worker, maintenance worker, integration runtime worker, integration validation worker, analytics worker, reports worker, forecasting worker, resolver execution worker, resolver maintenance worker, and exactly one Celery Beat service. It accepts a configurable `KAORI_ENV_FILE`, defaulting to `.env.production` for existing workflows.

`deploy/vps/compose.vps.yml` adds digest-pinned PostgreSQL and Redis services on the existing private `kaori_production` network. Neither state service publishes a host port. Both use named volumes, restart policies, authentication, and health checks.

The VPS production environment is stored at `/etc/kaori/.env.production`. It is created from `.env.production.example` by the operator, contains real secrets and long-lived operational configuration only on the server, is readable by the dedicated deploy user, and uses mode `0600`. Ordinary releases preserve this file. Release identity is not persistent host configuration and must not require an operator to edit this file for every release.

The following values are deployment-supplied runtime identity rather than persistent server configuration:

- `KAORI_IMAGE` — exact digest-qualified application image selected from governed RC evidence;
- `APP_VERSION` — intentional RC or stable SemVer identity selected by the governed release workflow;
- `APP_BUILD_SHA` — exact accepted source SHA;
- `APP_BUILD_DATE` — immutable image creation timestamp resolved from the pulled image when available.

Compose explicitly injects these values into the application containers so they override any accidental stale values in an older host environment file. `.env.production.example` documents that these values are deployment-managed and does not require operators to maintain release-specific values there.

## Deployment transaction
A deployment accepts only an image reference containing `@sha256:<64 lowercase hex characters>`, an exact 40-character lowercase source SHA, and a governed release version. Mutable-only tags and `latest` are rejected as deployment authority.

The deployment script validates prerequisites and environment permissions, creates an ephemeral `DOCKER_CONFIG`, reads registry username/password from standard input, authenticates with `docker login --password-stdin`, and removes the temporary Docker credential directory through an exit trap.

After pulling the immutable application image, the deployment script verifies the image OCI revision against the requested source SHA and resolves the image creation timestamp. It exports the release identity only for the current Compose transaction. It never rewrites `/etc/kaori/.env.production` as part of an ordinary release.

The sequence is:

1. Validate immutable image, source SHA, release version, and server environment permissions.
2. Authenticate ephemerally and pull the exact application image digest.
3. Verify the image OCI revision and resolve runtime release metadata.
4. Validate Compose with persistent configuration plus deployment-supplied release identity.
5. Start PostgreSQL and Redis only.
6. Wait for dependency health.
7. If an existing database schema is present, create a timestamped pre-migration PostgreSQL backup.
8. Run the production environment validator using the deployment-supplied release identity.
9. Run the one-shot database migration.
10. Start the complete application graph from the exact immutable image.
11. Verify all expected services, exact image identity, worker queues, single Beat, and loopback web readiness.
12. Record exact source SHA, release version, current image digest, previous release identity, migration result, deployment timestamp, and verification result under the server deployment-state directory.

A failed validation, dependency health check, backup, migration, or readiness check fails the deployment closed. Automatic destructive database restore is not performed.

## Backup, restore, and rollback
`backup.sh` writes PostgreSQL custom-format dumps to a restricted server backup directory and records a SHA256 checksum. `restore.sh` requires an explicit backup file, verifies the checksum when available, and restores through PostgreSQL tooling after an operator has intentionally selected the recovery point.

`rollback.sh` reads the recorded previous immutable image, previous source SHA, and previous release version and invokes the same governed deploy path. Image rollback is explicitly distinct from database rollback. If the failed rollout included an incompatible migration, the operator must pair image rollback with the reviewed database restore procedure.

## Remote delivery workflow
`.github/workflows/deploy-uat-vps.yml` is manual-only (`workflow_dispatch`). It is dispatched from `kaori/staging` with one human-facing input: an intentional `candidate_tag` previously published by the RC workflow.

Before SSH is opened, the workflow verifies that the requested tag is a GitHub prerelease, resolves its exact source SHA, proves that source equals current admitted `kaori/staging`, finds exact successful `quality.yml` evidence, finds successful RC publication evidence, and loads the unexpired `staging-image-<sha>` artifact. The artifact supplies the immutable application image digest. The workflow then passes the resolved image digest, accepted source SHA, and candidate version to the remote deploy script.

SSH uses:
- `KAORI_VPS_SSH_PRIVATE_KEY` secret;
- `KAORI_VPS_SSH_PASSPHRASE` secret;
- `KAORI_VPS_KNOWN_HOSTS` secret containing the pinned host key;
- repository/environment variables for host, user, port, and deployment root.

The encrypted RSA key is loaded into an ephemeral `ssh-agent` with an ephemeral `SSH_ASKPASS` helper. The workflow uses `StrictHostKeyChecking=yes` and the supplied known-hosts file. `StrictHostKeyChecking=no` is prohibited.

The workflow copies only the deployment bundle needed by the VPS, then invokes the remote deploy script. Registry credentials are consumed from GitHub Secrets and streamed to the remote script over the encrypted SSH session; they are not persisted in repository content or a long-lived server Docker config.

## Single active VPS slot
The current environment has one physical VPS and one active KAORI Compose project. A newer staging/RC deployment replaces the active image. Parallel staging and production stacks are intentionally out of scope. Current and previous immutable image, source SHA, and release version identities are recorded so the previous candidate remains a coherent rollback target.

## Ingress dependency
Issue #49 proves `127.0.0.1:5000/health/ready` and full internal runtime health. Issue #50 subsequently owns Nginx, TLS/ACME, DNS, unknown-host rejection, public port minimization, SSH/firewall hardening, and external DAST. No public PostgreSQL, Redis, Docker API, or direct KAORI application port is introduced by this design.

## Validation
Work-branch validation is the path-aware Developer Check. The contract under `tests/contracts/release/test_uat_vps_deployment_contract.py` locks the deployment boundary, immutable image policy, persistent-vs-release environment boundary, private state services, ephemeral registry authentication, backup/restore/rollback ownership, loopback readiness, and pinned SSH host verification.

After merge to `kaori/staging`, comprehensive KAORI CI is authoritative. Actual VPS UAT remains separate evidence and does not authorize `main` promotion without explicit maintainer acceptance under Issue #51.
