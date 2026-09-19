# KAORI VPS Compose Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the complete governed VPS deployment surface for Issue #49 without weakening KAORI CI, runtime hardening, secret boundaries, or the staging-to-main acceptance model.

**Architecture:** Keep `compose.production.yml` as the canonical KAORI application graph, extend it only to support a server-side environment-file path, and add a `deploy/vps/` overlay for private persistent PostgreSQL/Redis plus focused deploy/verify/backup/restore/rollback scripts. Add a manual GitHub Actions workflow that transfers the deployment bundle over pinned-host-key SSH and streams registry credentials into an ephemeral server-side Docker login.

**Tech Stack:** Docker Compose, Bash, PostgreSQL 16, Redis 7, OpenSSH, GitHub Actions, pytest contracts.

**Spec:** `docs/superpowers/specs/2026-09-02-vps-compose-deployment-design.md`

## Global Constraints

- VPS deployment tooling lives under `deploy/vps/`, never under `ops/github-runner/`.
- Production runtime code must not depend on `deploy/`.
- The real environment file is `/etc/kaori/.env.production`, server-side only, mode `0600`.
- Deployment accepts only digest-qualified images containing `@sha256:<64 lowercase hex>`.
- Registry authentication uses `docker login --password-stdin` and an ephemeral `DOCKER_CONFIG`.
- SSH requires an encrypted RSA key and pinned known-hosts material; `StrictHostKeyChecking=no` is forbidden.
- PostgreSQL and Redis publish no host ports.
- A pre-migration PostgreSQL backup is mandatory when an existing KAORI schema is present.
- Image rollback and database rollback remain separate operator decisions.
- Work branch uses Developer Check; comprehensive validation is staging-only.
- No `main` promotion or production UAT acceptance is performed by this implementation.

---

### Task 1: Lock the deployment boundary with a failing contract

**Files:**
- Create: `tests/contracts/platform_operations/test_vps_deployment_surface_contract.py`

**Interfaces:**
- Consumes: repository layout at the admitted staging baseline.
- Produces: contract requirements for all later files.

- [x] **Step 1: Write the failing contract**

The committed contract requires `deploy/vps/compose.vps.yml`, `deploy.sh`, `verify.sh`, `backup.sh`, `restore.sh`, `rollback.sh`, `README.md`, external env support in `compose.production.yml`, and `.github/workflows/deploy-uat-vps.yml`.

- [x] **Step 2: Freeze the RED SHA**

Commit: `d4272139c52d5d95c9b7ee131d35a5cb517576e7`.

- [ ] **Step 3: Record Developer Check RED evidence**

Expected: Developer Check fails because the required VPS deployment files and external env-file support do not exist yet. Keep this exact SHA frozen until the check concludes.

---

### Task 2: Support the server-side production environment path

**Files:**
- Modify: `compose.production.yml`

**Interfaces:**
- Consumes: `KAORI_ENV_FILE` optional environment variable.
- Produces: all KAORI services load `${KAORI_ENV_FILE:-.env.production}` through the existing Compose anchor.

- [ ] **Step 1: Change the anchor env file**

Replace:

```yaml
env_file:
  - .env.production
```

with:

```yaml
env_file:
  - ${KAORI_ENV_FILE:-.env.production}
```

- [ ] **Step 2: Preserve existing image and loopback contracts**

Keep `${KAORI_IMAGE:?Set KAORI_IMAGE in .env.production}` and the `127.0.0.1` default bind unchanged.

---

### Task 3: Add private persistent VPS state services

**Files:**
- Create: `deploy/vps/compose.vps.yml`

**Interfaces:**
- Consumes: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD` from `/etc/kaori/.env.production` through Compose interpolation.
- Produces: healthy `postgres` and `redis` services on `kaori_production`, with named volumes `kaori_vps_postgres` and `kaori_vps_redis`.

- [ ] **Step 1: Define PostgreSQL**

Use `postgres:16`, `restart: unless-stopped`, no `ports`, persistent `/var/lib/postgresql/data`, and `pg_isready` health using container environment variables.

- [ ] **Step 2: Define Redis**

Use `redis:7`, `restart: unless-stopped`, no `ports`, append-only persistence, and a shell command that expands `REDIS_PASSWORD` inside the container rather than embedding the secret into repository content.

- [ ] **Step 3: Add named volumes**

Declare explicit volume names so ordinary Compose recreation does not delete state.

---

### Task 4: Add backup and restore primitives

**Files:**
- Create: `deploy/vps/backup.sh`
- Create: `deploy/vps/restore.sh`

**Interfaces:**
- Consumes: `KAORI_ENV_FILE`, base/overlay compose paths, PostgreSQL environment values.
- Produces: timestamped custom-format PostgreSQL dump + `.sha256`, and explicit restore command for a selected dump.

- [ ] **Step 1: Implement backup**

Use `docker compose ... exec -T postgres pg_dump --format=custom`, write to `${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}`, set restrictive umask, and write a SHA256 sidecar.

- [ ] **Step 2: Implement restore**

Require an explicit dump path, verify its sidecar when present, refuse missing files, and run `pg_restore --clean --if-exists --no-owner` through the PostgreSQL service.

---

### Task 5: Implement transactional digest deployment

**Files:**
- Create: `deploy/vps/deploy.sh`

**Interfaces:**
- Consumes positional `IMAGE@sha256:...` and source SHA; reads registry username/password as two lines from stdin; uses `/etc/kaori/.env.production` by default.
- Produces active Compose rollout plus deployment-state files `current-image`, `previous-image`, `source-sha`, `migration-result`, `verification-result`, `deployed-at`.

- [ ] **Step 1: Validate inputs and host files**

Require root tools (`docker`, `sha256sum`, `curl`), exact image digest syntax, 40-hex source SHA, readable mode-0600 environment file, and valid deploy directories.

- [ ] **Step 2: Authenticate ephemerally**

Create `DOCKER_CONFIG="$(mktemp -d)"`, register an exit trap that removes it, derive the registry host from the image reference, and authenticate with `docker login --username "$registry_user" --password-stdin`.

- [ ] **Step 3: Start dependencies and validate**

Pull the exact digest, start `postgres redis`, wait for both health checks, then run `docker compose ... run --rm validate`.

- [ ] **Step 4: Protect migration state**

If `alembic_version` exists, invoke `backup.sh` before migration. Then run `docker compose ... run --rm migrate` and record success only after exit code zero.

- [ ] **Step 5: Start and verify full runtime**

Run `docker compose ... up -d` for the application graph and invoke `verify.sh`.

- [ ] **Step 6: Commit deployment evidence on the host**

Atomically move existing `current-image` to `previous-image`, then write the new immutable image, source SHA, timestamp, migration and verification results.

---

### Task 6: Add full runtime verifier and rollback

**Files:**
- Create: `deploy/vps/verify.sh`
- Create: `deploy/vps/rollback.sh`

**Interfaces:**
- `verify.sh` consumes the active Compose project and checks state services, all canonical workers, Beat, and `http://127.0.0.1:5000/health/ready`.
- `rollback.sh` consumes recorded `previous-image` and source SHA, then reuses `deploy.sh`; it does not silently restore a database.

- [ ] **Step 1: Verify dependencies and application services**

Fail unless every expected service exists/runs and PostgreSQL/Redis report healthy.

- [ ] **Step 2: Verify loopback readiness**

Use `curl --fail --silent --show-error --max-time 10 http://127.0.0.1:5000/health/ready`.

- [ ] **Step 3: Implement rollback**

Read and revalidate the recorded previous digest, require an explicit source SHA argument for the rollback target, print the database-rollback warning, and pipe fresh registry credentials to the same deploy script.

---

### Task 7: Add manual pinned-SSH UAT deployment workflow

**Files:**
- Create: `.github/workflows/deploy-uat-vps.yml`

**Interfaces:**
- Consumes workflow inputs `image`, `source_sha`; GitHub Secrets `KAORI_VPS_SSH_PRIVATE_KEY`, `KAORI_VPS_SSH_PASSPHRASE`, `KAORI_VPS_SSH_KNOWN_HOSTS`, `KAORI_DOCKER_REGISTRY_USERNAME`, `KAORI_DOCKER_REGISTRY_PASSWORD`; vars `KAORI_VPS_HOST`, `KAORI_VPS_USER`, `KAORI_VPS_PORT`.
- Produces remote deployment invocation on the single UAT VPS.

- [ ] **Step 1: Restrict dispatch authority**

Use `workflow_dispatch`, fail unless the selected workflow ref is `kaori/staging`, and validate the current remote staging SHA equals input `source_sha`.

- [ ] **Step 2: Configure SSH safely**

Create temporary key and known-hosts files with restrictive mode, start `ssh-agent`, load the encrypted RSA key through an ephemeral `SSH_ASKPASS` helper, and use `StrictHostKeyChecking=yes` plus the explicit known-hosts file for every SSH/SCP operation.

- [ ] **Step 3: Transfer only deployment inputs**

Copy `compose.production.yml` and `deploy/vps/` to a versioned temporary remote directory and atomically refresh the current deployment-tool directory.

- [ ] **Step 4: Stream registry credentials**

Pipe exactly two lines (username, password) into the remote `deploy.sh`; rely on GitHub masking and disable shell tracing.

---

### Task 8: Document operator lifecycle

**Files:**
- Create: `deploy/vps/README.md`

**Interfaces:**
- Produces the authoritative operator runbook for server preparation, env creation, GitHub Secrets/variables, deployment, verification, backup/restore, rollback, and Issue #50 handoff.

- [ ] **Step 1: Document one-time server preparation**

Explain dedicated deploy user, Docker privilege, `/etc/kaori/.env.production` creation from `.env.production.example`, permission `0600`, private Compose state, and backup/state directories.

- [ ] **Step 2: Document GitHub configuration**

List the exact required Secrets and variables without example secret values.

- [ ] **Step 3: Document failure/recovery semantics**

Make explicit that image rollback does not reverse schema changes and when restore is required.

---

### Task 9: Verify GREEN and integrate only after evidence

**Files:**
- Test: `tests/contracts/platform_operations/test_vps_deployment_surface_contract.py`

**Interfaces:**
- Produces the frozen GREEN candidate for PR-to-staging integration.

- [ ] **Step 1: Run Developer Check**

Expected: Route Checks PASS and Developer Check PASS on the exact implementation SHA.

- [ ] **Step 2: Review PR diff and security boundaries**

Confirm no credentials, no `StrictHostKeyChecking=no`, no public DB/Redis ports, and no runner/deploy ownership overlap.

- [ ] **Step 3: Merge to `kaori/staging` only after GREEN**

After integration, comprehensive KAORI CI is authoritative. Do not close #49 until actual authenticated pull-by-digest and VPS runtime/UAT evidence exists.
