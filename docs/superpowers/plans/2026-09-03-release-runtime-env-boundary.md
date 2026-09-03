# Release Runtime Environment Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `/etc/kaori/.env.production` stable across releases while the governed deployment supplies immutable image/version/source metadata ephemerally to Compose and records coherent rollback identity.

**Architecture:** The server env file remains the long-lived configuration/secrets authority. `deploy.sh` receives the immutable image, exact source SHA, and governed release version, derives the immutable image creation timestamp, exports release metadata for the current Compose transaction, and never rewrites the persistent env file. `compose.production.yml` explicitly injects release metadata into all application containers so explicit runtime values override `env_file`; rollback stores and restores image, source SHA, and version together.

**Tech Stack:** Bash, Docker Compose, GitHub Actions, Python/pytest contract tests.

**Spec:** `docs/superpowers/specs/2026-09-02-vps-compose-deployment-design.md`

## Global Constraints

- Issue authority is #49; branch is `kaori/task-49-release-env-boundary`; target is `kaori/staging`.
- `/etc/kaori/.env.production` remains mode `0600`, operator-managed, and unchanged by ordinary release deployment.
- Application deployment authority remains digest-qualified `KAORI_IMAGE` plus exact accepted source SHA; mutable-only tags and `latest` are not deployment authority.
- UAT remains `candidate_tag` → prerelease/evidence validation → immutable digest → SSH deploy; no free-form image deployment path is introduced.
- Rollback must restore coherent previous image, source SHA, release version, and reviewed database backup.
- Work branch uses Developer Check; only admitted `kaori/staging` may cut the next intentional RC.

---

### Task 1: Lock the persistent-vs-release environment contract

**Files:**
- Modify: `tests/contracts/release/test_uat_vps_deployment_contract.py`
- Modify: `tests/contracts/release/test_environment_configuration_contract.py`

**Interfaces:**
- Consumes: current `compose.production.yml`, `.env.production.example`, `deploy/vps/deploy.sh`, `deploy/vps/rollback.sh`, `.github/workflows/deploy-uat-vps.yml`.
- Produces: failing contract assertions requiring release metadata to be absent from persistent env, injected by Compose, passed by workflow/deploy, and preserved for rollback.

- [ ] **Step 1: Add RED assertions**

Add assertions that `.env.production.example` does not contain assignments for `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, or `APP_BUILD_DATE`; that `compose.production.yml` explicitly maps all four variables from deployment environment; that `deploy.sh` requires a third release-version argument and exports all four runtime identity values; that workflow passes `candidate_tag` to `deploy.sh`; and that rollback requires a previous-version state file.

- [ ] **Step 2: Run focused RED contract**

Run:

```bash
pytest -q \
  tests/contracts/release/test_uat_vps_deployment_contract.py \
  tests/contracts/release/test_environment_configuration_contract.py
```

Expected: FAIL only on the new release-environment boundary assertions because current production files still persist or omit those responsibilities.

- [ ] **Step 3: Commit RED authority**

```bash
git add \
  tests/contracts/release/test_uat_vps_deployment_contract.py \
  tests/contracts/release/test_environment_configuration_contract.py
git commit -m "test(deploy): lock runtime release env boundary #49"
```

### Task 2: Inject release identity without mutating persistent env

**Files:**
- Modify: `.env.production.example`
- Modify: `compose.production.yml`
- Modify: `deploy/vps/deploy.sh`
- Modify: `.github/workflows/deploy-uat-vps.yml`

**Interfaces:**
- Consumes: `deploy.sh IMAGE@sha256:<digest> SOURCE_SHA RELEASE_VERSION`.
- Produces: exported `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, `APP_BUILD_DATE` for Compose; all application containers receive those values explicitly.

- [ ] **Step 1: Remove release assignments from persistent template**

Replace the release-specific top-of-file assignments with comments stating that `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` are supplied by governed deployment and must not be maintained manually in `/etc/kaori/.env.production`.

- [ ] **Step 2: Make Compose explicit runtime identity authority**

In `x-kaori-image.environment`, preserve `APP_ENV: production` and add:

```yaml
KAORI_IMAGE: ${KAORI_IMAGE:?KAORI_IMAGE is supplied by governed deployment}
APP_VERSION: ${APP_VERSION:?APP_VERSION is supplied by governed deployment}
APP_BUILD_SHA: ${APP_BUILD_SHA:?APP_BUILD_SHA is supplied by governed deployment}
APP_BUILD_DATE: ${APP_BUILD_DATE:?APP_BUILD_DATE is supplied by governed deployment}
```

This explicit `environment` block overrides any accidental stale value in `env_file`.

- [ ] **Step 3: Extend deploy transaction identity**

Change `deploy.sh` usage to exactly three arguments: digest-qualified image, 40-character source SHA, and SemVer/RC release version matching `^v?[0-9]+\.[0-9]+\.[0-9]+(?:-rc\.[0-9]+)?$`. After pulling the image and proving `org.opencontainers.image.revision` equals the source SHA, inspect `.Created`, require a non-empty timestamp, then export:

```bash
export KAORI_IMAGE="$image"
export APP_VERSION="$release_version"
export APP_BUILD_SHA="$source_sha"
export APP_BUILD_DATE="$image_created"
```

Do not write these values into `/etc/kaori/.env.production`.

- [ ] **Step 4: Pass the governed candidate version from workflow**

In `deploy-uat-vps.yml`, expose `REQUESTED_VERSION` from `needs.admission.outputs.candidate_tag`, include it in the quoted remote payload, and invoke:

```bash
bash "$deploy_script" "$requested_image" "$requested_sha" "$requested_version"
```

- [ ] **Step 5: Run focused GREEN contract**

Run the same focused pytest command from Task 1. Expected: release-env assertions pass except rollback assertions, which remain RED until Task 3.

### Task 3: Preserve coherent rollback release identity

**Files:**
- Modify: `deploy/vps/deploy.sh`
- Modify: `deploy/vps/rollback.sh`
- Modify: `tests/contracts/release/test_uat_vps_deployment_contract.py`

**Interfaces:**
- Consumes: deployment-state `current-version`, `previous-version` alongside image/source records.
- Produces: rollback invocation with previous immutable image, previous source SHA, and previous release version.

- [ ] **Step 1: Record current and previous version**

When recording deployment state, copy an existing `current-version` to `previous-version`, then write the current `release_version` to `current-version` with the same restrictive state-file permissions as image/source records.

- [ ] **Step 2: Require previous version during rollback**

Add `previous_version_file="$KAORI_STATE_DIR/previous-version"`, require it readable, validate its SemVer/RC form, and call:

```bash
exec bash "$SCRIPT_DIR/deploy.sh" \
  "$previous_image_ref" \
  "$previous_source_sha" \
  "$previous_version"
```

- [ ] **Step 3: Run focused GREEN contract**

Run:

```bash
pytest -q \
  tests/contracts/release/test_uat_vps_deployment_contract.py \
  tests/contracts/release/test_environment_configuration_contract.py
```

Expected: PASS.

### Task 4: Align operator documentation and verify release gates

**Files:**
- Modify: `deploy/vps/README.md`
- Modify: `docs/superpowers/specs/2026-09-02-vps-compose-deployment-design.md`

**Interfaces:**
- Consumes: implemented deployment behavior.
- Produces: operator contract stating persistent env is one-time/long-lived and release identity is deployment-managed.

- [ ] **Step 1: Update VPS README**

Document that `/etc/kaori/.env.production` contains long-lived secrets/configuration and immutable PostgreSQL/Redis dependency digests, while application `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` are not edited for ordinary releases. Explain that a fresh RC deployment requires only the governed `candidate_tag`; workflow resolves digest and runtime identity.

- [ ] **Step 2: Run release-focused verification**

Run:

```bash
pytest -q \
  tests/contracts/release/test_uat_vps_deployment_contract.py \
  tests/contracts/release/test_environment_configuration_contract.py \
  tests/contracts/release/test_staging_image_publish_contract.py
python scripts/verify_environment_contract.py
ruff check \
  tests/contracts/release/test_uat_vps_deployment_contract.py \
  tests/contracts/release/test_environment_configuration_contract.py
ruff format --check \
  tests/contracts/release/test_uat_vps_deployment_contract.py \
  tests/contracts/release/test_environment_configuration_contract.py
```

Expected: all commands exit `0`.

- [ ] **Step 3: Run path-aware Developer Check**

Push the final branch SHA and require the repository Developer Check to pass before PR integration to `kaori/staging`.

- [ ] **Step 4: Staging admission and fresh RC**

After PR merge, require Full Admission on the exact new staging SHA. RC `v0.1.0-rc.3` remains historical and must not be deployed because it predates this contract. Cut a fresh intentional RC only from the newly admitted staging SHA, then resume #49 VPS UAT.
