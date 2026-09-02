# KAORI UAT VPS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a governed, immutable-RC-only deployment path for running the complete KAORI production Compose graph with PostgreSQL and Redis on the single UAT VPS.

**Architecture:** Keep `compose.production.yml` as the canonical application graph and add a separate `deploy/vps/compose.vps.yml` dependency overlay. GitHub Actions resolves trusted RC evidence before SSH, uses encrypted RSA/pinned known-hosts trust, transfers only exact deployment assets, performs ephemeral registry authentication on the VPS, and invokes focused deploy/verify/backup/restore/rollback scripts. Real application secrets remain in `/etc/kaori/.env.production`.

**Tech Stack:** GitHub Actions, Bash, Docker Engine, Docker Compose v2, PostgreSQL, Redis, Flask/Celery production image, SSH/OpenSSH.

**Spec:** `docs/superpowers/specs/2026-09-02-uat-vps-deployment-design.md`

## Global Constraints

- Work from exact admitted staging SHA `fac90128b638e1734e8d6af3ed00c6626081f773`.
- `deploy/vps/` is separate from `ops/github-runner/`.
- Work branch receives Developer Check only; comprehensive runtime/security authority starts after merge to `kaori/staging`.
- No real VPS UAT deployment occurs until a fresh intentional RC and required GitHub Environment secrets/variables are available and human UAT is authorized.
- No promotion to `main` or stable release is part of this plan.
- Application rollout authority must be an immutable `registry/image@sha256:<64 hex>` reference resolved from RC publication evidence.
- Real `/etc/kaori/.env.production` and SSH/registry secrets never enter Git, release artifacts, or production image content.
- `StrictHostKeyChecking=no`, free-form mutable image tags, embedded credentials, and public PostgreSQL/Redis ports are prohibited.

---

### Task 1: Lock the VPS deployment contract with RED tests

**Files:**
- Create: `tests/contracts/release/test_uat_vps_deployment_contract.py`

**Interfaces:**
- Consumes: approved design specification and current production Compose/release workflow contracts.
- Produces: a contract that fails until the deployment surface, workflow trust boundary, environment behavior, and data-safety ordering exist.

- [ ] **Step 1: Write contract tests for repository ownership and required files**

Require:

```python
VPS_ROOT = ROOT / "deploy" / "vps"
REQUIRED_VPS_FILES = {
    "README.md",
    "compose.vps.yml",
    "deploy.sh",
    "verify.sh",
    "backup.sh",
    "restore.sh",
    "rollback.sh",
}
```

Assert every file exists and assert `ops/github-runner/vps-deploy` does not exist.

- [ ] **Step 2: Lock production Compose environment-file indirection**

Assert `compose.production.yml` contains `${KAORI_ENV_FILE:-.env.production}` and still requires `${KAORI_IMAGE:` rather than a built/local image fallback.

- [ ] **Step 3: Lock private dependency topology**

Parse/read `deploy/vps/compose.vps.yml` and assert it defines `postgres` and `redis`, has named data volumes, healthchecks, restart policy, no `ports:` for either dependency, and requires `KAORI_POSTGRES_IMAGE` / `KAORI_REDIS_IMAGE`.

- [ ] **Step 4: Lock workflow trust and RC authority**

Assert `.github/workflows/deploy-uat-vps.yml` contains all of:

```text
environment: uat
workflow_dispatch
candidate_tag
KAORI_VPS_SSH_PRIVATE_KEY
KAORI_VPS_SSH_PASSPHRASE
KAORI_VPS_KNOWN_HOSTS
StrictHostKeyChecking=yes
UserKnownHostsFile
ssh-agent
SSH_ASKPASS_REQUIRE=force
KAORI_DOCKER_REGISTRY_USERNAME
KAORI_DOCKER_REGISTRY_PASSWORD
--password-stdin
staging-image-
publish-staging-image.yml
quality.yml
@sha256:
```

Assert forbidden text is absent:

```text
StrictHostKeyChecking=no
--password ${{
latest
```

where the `latest` check is scoped to image selection/pull logic, not prose.

- [ ] **Step 5: Lock deploy ordering**

Assert `deploy.sh` places operations in this order:

```text
start_dependencies
wait_for_dependencies
existing_database_requires_backup
run_validate
run_migrate
start_application_services
run_verify
record_deployment
```

and does not call `docker build`.

- [ ] **Step 6: Lock backup/restore/rollback fail-closed behavior**

Assert:

- `backup.sh` uses PostgreSQL custom-format `pg_dump`;
- `restore.sh` validates the backup path and stops application services before database replacement;
- `rollback.sh` reads the previous immutable image and requires database restore when recorded migration backup evidence exists.

- [ ] **Step 7: Run focused contract and capture semantic RED**

Run through a Draft PR so Developer Check executes:

```bash
pytest -q --tb=short tests/contracts/release/test_uat_vps_deployment_contract.py
```

Expected: failures caused by missing `deploy/vps/*`, missing workflow, and missing `KAORI_ENV_FILE` indirection—not formatter/lint failures.

- [ ] **Step 8: Commit RED contract**

```bash
git add tests/contracts/release/test_uat_vps_deployment_contract.py
git commit -m "test(deploy): lock governed UAT VPS deployment #49"
```

---

### Task 2: Add the VPS Compose dependency boundary

**Files:**
- Modify: `compose.production.yml`
- Modify: `.env.production.example`
- Create: `deploy/vps/compose.vps.yml`

**Interfaces:**
- Consumes: `KAORI_ENV_FILE`, `KAORI_POSTGRES_IMAGE`, `KAORI_REDIS_IMAGE`, PostgreSQL/Redis credentials from the host env file.
- Produces: canonical application graph plus private persistent PostgreSQL/Redis overlay.

- [ ] **Step 1: Make production service env-file path configurable without breaking default behavior**

Change:

```yaml
env_file:
  - .env.production
```

to:

```yaml
env_file:
  - ${KAORI_ENV_FILE:-.env.production}
```

Do not alter application service topology.

- [ ] **Step 2: Add VPS dependency settings to the example env**

Document:

```dotenv
KAORI_POSTGRES_IMAGE=postgres:17-bookworm@sha256:<operator-reviewed-digest>
KAORI_REDIS_IMAGE=redis:7-bookworm@sha256:<operator-reviewed-digest>
POSTGRES_DB=kaori
POSTGRES_USER=kaori
POSTGRES_PASSWORD=
REDIS_PASSWORD=
DATABASE_URL=postgresql://kaori:<url-encoded-password>@postgres:5432/kaori
REDIS_URL=redis://:<url-encoded-password>@redis:6379/0
CELERY_BROKER_URL=redis://:<url-encoded-password>@redis:6379/1
RATELIMIT_STORAGE_URI=redis://:<url-encoded-password>@redis:6379/2
CELERY_RESULT_BACKEND=redis://:<url-encoded-password>@redis:6379/3
```

Keep placeholders only in the example env where operator values are intentionally required; implementation code must contain no unresolved TODO/TBD.

- [ ] **Step 3: Add PostgreSQL service**

`deploy/vps/compose.vps.yml` defines:

```yaml
services:
  postgres:
    image: ${KAORI_POSTGRES_IMAGE:?Set immutable KAORI_POSTGRES_IMAGE in the host environment}
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:?Set POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER:?Set POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}
    volumes:
      - kaori_vps_postgres_data:/var/lib/postgresql/data
    networks:
      - kaori_production
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
```

No `ports` field.

- [ ] **Step 4: Add authenticated persistent Redis service**

Use an environment-expanded container command so the Compose source does not contain the credential value:

```yaml
  redis:
    image: ${KAORI_REDIS_IMAGE:?Set immutable KAORI_REDIS_IMAGE in the host environment}
    restart: unless-stopped
    environment:
      REDIS_PASSWORD: ${REDIS_PASSWORD:?Set REDIS_PASSWORD}
    command:
      - sh
      - -ec
      - exec redis-server --appendonly yes --requirepass "$$REDIS_PASSWORD"
    volumes:
      - kaori_vps_redis_data:/data
    networks:
      - kaori_production
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a \"$$REDIS_PASSWORD\" --no-auth-warning ping | grep -qx PONG"]
```

No `ports` field.

- [ ] **Step 5: Declare named volumes**

```yaml
volumes:
  kaori_vps_postgres_data:
    name: kaori-vps-postgres-data
  kaori_vps_redis_data:
    name: kaori-vps-redis-data
```

- [ ] **Step 6: Run contract tests**

Expected: topology/env tests turn GREEN while deployment/workflow tests remain RED.

- [ ] **Step 7: Commit Compose boundary**

```bash
git add compose.production.yml .env.production.example deploy/vps/compose.vps.yml
git commit -m "feat(deploy): add private VPS dependency topology #49"
```

---

### Task 3: Implement backup and restore safety surfaces

**Files:**
- Create: `deploy/vps/backup.sh`
- Create: `deploy/vps/restore.sh`

**Interfaces:**
- Consumes: `KAORI_ENV_FILE`, `KAORI_BASE_COMPOSE`, `KAORI_VPS_COMPOSE`, `KAORI_BACKUP_DIR` and a healthy `postgres` Compose service.
- Produces: timestamped custom-format PostgreSQL dump; explicit controlled restore operation.

- [ ] **Step 1: Add shared Compose invocation pattern in each focused script**

Use:

```bash
compose=(
  docker compose
  --env-file "$KAORI_ENV_FILE"
  --file "$KAORI_BASE_COMPOSE"
  --file "$KAORI_VPS_COMPOSE"
)
```

Scripts validate required files and directories before mutation.

- [ ] **Step 2: Implement custom-format backup**

`backup.sh` obtains `POSTGRES_USER` and `POSTGRES_DB` from the running postgres container and writes:

```bash
"${compose[@]}" exec -T postgres pg_dump --format=custom --no-owner --no-privileges \
  --username "$db_user" "$db_name" > "$backup_file"
```

Require non-empty output, mode `0600`, then print only the resulting backup path.

- [ ] **Step 3: Implement guarded restore**

`restore.sh` requires exactly one backup path, resolves it with `readlink -f`, verifies it is inside `KAORI_BACKUP_DIR`, verifies non-empty file, and stops the long-running application service list before database mutation.

Terminate existing database sessions, recreate the application DB through the postgres service, then restore with:

```bash
pg_restore --no-owner --no-privileges --exit-on-error
```

- [ ] **Step 4: Ensure restore does not auto-start application services**

The script ends after successful database restore and explicitly prints that rollout/verification must be performed by `rollback.sh` or `deploy.sh`.

- [ ] **Step 5: Run contract tests and shell syntax checks available through Developer Check**

Expected: backup/restore assertions GREEN.

- [ ] **Step 6: Commit data-safety scripts**

```bash
git add deploy/vps/backup.sh deploy/vps/restore.sh
git commit -m "feat(deploy): add VPS database recovery tooling #49"
```

---

### Task 4: Implement deployment, verification, and rollback

**Files:**
- Create: `deploy/vps/deploy.sh`
- Create: `deploy/vps/verify.sh`
- Create: `deploy/vps/rollback.sh`

**Interfaces:**
- Consumes: exact RC source/image evidence, host env file, Compose files, running Docker daemon.
- Produces: validated full stack, deployment state, independently callable verification, guarded rollback.

- [ ] **Step 1: Define deployment defaults**

Use host defaults:

```bash
KAORI_ENV_FILE=${KAORI_ENV_FILE:-/etc/kaori/.env.production}
KAORI_STATE_DIR=${KAORI_STATE_DIR:-/opt/kaori/state}
KAORI_BACKUP_DIR=${KAORI_BACKUP_DIR:-/opt/kaori/backups/postgres}
```

Resolve base/overlay Compose paths relative to the source-addressed release directory.

- [ ] **Step 2: Validate immutable inputs and environment permissions**

Require:

```text
KAORI_SOURCE_SHA = 40 lowercase hex
KAORI_CANDIDATE_TAG = vN.N.N-rc.N
KAORI_IMAGE_REF = configured registry image@sha256:64-hex
```

Require the environment file exists and has no permissions for `other` and no group write/execute. Export `KAORI_IMAGE="$KAORI_IMAGE_REF"` and `KAORI_ENV_FILE` before Compose invocation.

- [ ] **Step 3: Validate Compose and dependency-image immutability**

Run `docker compose ... config --quiet` and fail unless `KAORI_POSTGRES_IMAGE` / `KAORI_REDIS_IMAGE` resolve to digest references.

- [ ] **Step 4: Start dependencies and wait for health**

Implement functions named exactly:

```text
start_dependencies
wait_for_dependencies
```

Pull/start only `postgres redis` first and poll Docker Compose health with a bounded timeout.

- [ ] **Step 5: Detect existing database and require backup**

Implement `existing_database_requires_backup`. Query PostgreSQL for non-system tables. If count is greater than zero, invoke `backup.sh` and capture its output path. Any failed backup aborts before migration.

- [ ] **Step 6: Run production validation and migration explicitly**

Implement in this exact order:

```text
run_validate
run_migrate
```

using one-shot Compose runs. Any non-zero exit aborts before long-running service replacement.

- [ ] **Step 7: Start the canonical application services**

Implement `start_application_services` with an explicit service array containing web, all nine worker roles, and Beat. Use `--pull never` so rollout cannot silently replace the already verified immutable application image.

- [ ] **Step 8: Implement independent verification**

`verify.sh` checks dependency health/no public ports, exact image identity for every KAORI long-running service, web Docker health + host loopback readiness, worker running state, canonical active queues, and exactly one Beat container.

`--restart-check` writes an instance-volume sentinel, restarts controlled services/dependencies, proves sentinel/data survival, then removes the sentinel.

- [ ] **Step 9: Record deployment state only after verification**

Implement `run_verify` then `record_deployment`. Atomically write `KAORI_STATE_DIR/current.env` containing current/previous image refs, source SHA, candidate tag, backup path, and successful verification timestamp. Preserve the prior state as `previous.env` before replacement.

- [ ] **Step 10: Implement guarded rollback**

`rollback.sh` reads the previous image from state, validates it is immutable, and refuses image-only rollback when the current deployment records a pre-migration backup. When `--restore-backup <exact-recorded-path>` is supplied, call `restore.sh`, then deploy the previous immutable image and verify it.

- [ ] **Step 11: Run contract tests**

Expected: all local deployment script contract assertions GREEN except workflow/docs checks not yet implemented.

- [ ] **Step 12: Commit runtime deployment tooling**

```bash
git add deploy/vps/deploy.sh deploy/vps/verify.sh deploy/vps/rollback.sh
git commit -m "feat(deploy): add governed VPS rollout lifecycle #49"
```

---

### Task 5: Add the governed GitHub UAT deployment workflow

**Files:**
- Create: `.github/workflows/deploy-uat-vps.yml`

**Interfaces:**
- Consumes: `candidate_tag` operator input, GitHub RC/release/action evidence, UAT environment SSH/registry secrets and VPS variables.
- Produces: pinned-trust SSH deployment of the exact published immutable RC plus GitHub job evidence.

- [ ] **Step 1: Define explicit manual boundary**

```yaml
name: KAORI UAT VPS Deploy
on:
  workflow_dispatch:
    inputs:
      candidate_tag:
        description: Intentional KAORI RC tag to deploy
        required: true
        type: string
```

No push trigger.

- [ ] **Step 2: Resolve and validate RC authority before SSH**

On `ubuntu-latest`, query GitHub API using `github.token` to require:

- matching GitHub prerelease;
- tag target source SHA;
- exact successful `quality.yml` run;
- exact successful `publish-staging-image.yml` run;
- `staging-image-<source_sha>` artifact.

Download/unzip the evidence and validate exact source/tag/registry-rooted digest reference.

- [ ] **Step 3: Prepare encrypted SSH identity**

Use `environment: uat` and environment secrets/variables. Create key/known-host files under `RUNNER_TEMP`, start `ssh-agent`, and load the passphrase-protected RSA key through a temporary `SSH_ASKPASS` helper. Require `StrictHostKeyChecking=yes` and the governed `UserKnownHostsFile` on every SSH/tar transport.

- [ ] **Step 4: Transfer exact deployment assets**

Tar only:

```text
compose.production.yml
deploy/vps/
```

and extract remotely to `/opt/kaori/releases/<source_sha>/`. Do not install Git or clone the repository on the VPS.

- [ ] **Step 5: Perform ephemeral remote registry login and deploy**

Pipe `KAORI_DOCKER_REGISTRY_PASSWORD` through SSH standard input to remote `docker login --password-stdin`, using a temporary remote `DOCKER_CONFIG`. In the same controlled remote shell, pull `KAORI_IMAGE_REF`, invoke the exact release `deploy/vps/deploy.sh`, then logout/remove the temporary Docker config via EXIT trap.

- [ ] **Step 6: Always clean SSH material**

Use an `if: always()` step to remove the private key, passphrase helper, known-hosts file, and agent keys.

- [ ] **Step 7: Run Developer Check workflow lint/contracts**

Because `.github/*` is changed, expect wide Developer Check including actionlint, Ruff/DjLint/Pyright/migrations/contracts/frontend formatting.

- [ ] **Step 8: Commit workflow**

```bash
git add .github/workflows/deploy-uat-vps.yml
git commit -m "feat(deploy): add governed UAT VPS workflow #49"
```

---

### Task 6: Document operator lifecycle and exact secret setup

**Files:**
- Create: `deploy/vps/README.md`

**Interfaces:**
- Consumes: implemented scripts/workflow and approved UAT infrastructure assumptions.
- Produces: operator runbook for host preparation, GitHub environment configuration, deployment, evidence review, recovery, and UAT handoff.

- [ ] **Step 1: Document one-time VPS preparation**

State required paths/ownership:

```text
/etc/kaori/.env.production
/opt/kaori/releases
/opt/kaori/state
/opt/kaori/backups/postgres
```

Require Docker Engine + Compose v2, operator-prepared non-root deploy user with Docker access, DNS deferred to #50, and restrictive env-file permissions.

- [ ] **Step 2: Document GitHub Environment `uat` configuration**

List exact secrets and variables from the design. Explicitly state the RSA public key is installed in the deploy user `authorized_keys` and `KAORI_VPS_KNOWN_HOSTS` must be captured/verified out of band before first deployment.

- [ ] **Step 3: Document server env setup**

Explain copying values from `.env.production.example` manually, using private `postgres`/`redis` service names, setting URL-encoded passwords in URLs, and selecting immutable dependency image digests.

- [ ] **Step 4: Document deployment/recovery sequence**

Describe:

```text
intentional RC -> manual KAORI UAT VPS Deploy -> backup -> validate -> migrate -> rollout -> verify -> optional restart-check -> UAT review
```

and explicit rollback/restore decision rules.

- [ ] **Step 5: Document #50 handoff**

State #49 acceptance stops at loopback readiness. Nginx/TLS/ACME/firewall/external HTTPS verification belongs to #50.

- [ ] **Step 6: Run final contract tests**

Expected: `test_uat_vps_deployment_contract.py` completely GREEN.

- [ ] **Step 7: Commit runbook**

```bash
git add deploy/vps/README.md
git commit -m "docs(deploy): add UAT VPS operator runbook #49"
```

---

### Task 7: Freeze candidate, obtain Developer Check GREEN, and integrate to staging

**Files:**
- No new feature files unless verification finds a defect.

**Interfaces:**
- Consumes: completed #49 work branch.
- Produces: exact frozen candidate with Developer Check evidence and staging comprehensive admission.

- [ ] **Step 1: Compare work branch against exact base**

Confirm branch is ahead of and not behind `fac90128b638e1734e8d6af3ed00c6626081f773`. Review every changed path and verify no unrelated application feature code changed.

- [ ] **Step 2: Obtain exact-SHA Developer Check GREEN**

The final candidate must pass the PR-triggered Developer Check. If source changes after the pass, obtain a new exact-SHA pass.

- [ ] **Step 3: Update PR evidence**

Record:

- base staging SHA;
- semantic RED SHA/run;
- final candidate SHA;
- Developer Check run/result;
- changed-file boundary;
- security/data impact;
- explicit statement that actual remote VPS deployment remains pending UAT secrets/fresh RC.

- [ ] **Step 4: Merge exact frozen candidate to `kaori/staging`**

Use exact-head guard. Do not cut an RC automatically and do not deploy the VPS as part of the merge.

- [ ] **Step 5: Require comprehensive staging KAORI CI success**

Capture Full Admission artifact, runtime/DAST evidence, and exact staging merge SHA.

- [ ] **Step 6: Update Issue #49 status without falsely closing remote acceptance**

If repository/tooling acceptance is admitted but actual SSH/full-stack VPS UAT has not run because secrets/RC/operator preparation are pending, leave #49 OPEN with precise completed-vs-pending evidence. Close only after the remote UAT acceptance criteria are actually proven.