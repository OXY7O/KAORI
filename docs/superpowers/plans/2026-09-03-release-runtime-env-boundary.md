# Release Runtime Environment Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `/etc/kaori/.env.production` stable across releases while the governed deployment supplies immutable image/version/source metadata ephemerally to Compose and records coherent rollback identity.

**Architecture:** The server env file remains the long-lived configuration/secrets authority. `deploy.sh` receives the immutable image, exact source SHA, and governed Git release tag, derives the immutable image creation timestamp, normalizes the tag to application SemVer by removing the leading `v`, exports release metadata for the current Compose transaction, and never rewrites the persistent env file. `compose.production.yml` explicitly injects release metadata into all application containers so explicit runtime values override `env_file`; rollback stores and restores image, source SHA, and governed release tag together.

**Tech Stack:** Bash, Docker Compose, GitHub Actions, Python/pytest contract tests.

**Spec:** `docs/superpowers/specs/2026-09-02-vps-compose-deployment-design.md`

## Global Constraints

- Issue authority is #49; branch is `kaori/task-49-release-env-boundary`; target is `kaori/staging`.
- `/etc/kaori/.env.production` remains mode `0600`, operator-managed, and unchanged by ordinary release deployment.
- Application deployment authority remains digest-qualified `KAORI_IMAGE` plus exact accepted source SHA; mutable-only tags and `latest` are not deployment authority.
- UAT remains `candidate_tag` → prerelease/evidence validation → immutable digest → SSH deploy; no free-form image deployment path is introduced.
- Governed release tags retain `vX.Y.Z` / `vX.Y.Z-rc.N`; application `APP_VERSION` is normalized to `X.Y.Z` / `X.Y.Z-rc.N` without `v`.
- Rollback must restore coherent previous image, source SHA, governed release version, and reviewed database backup.
- Work branch uses Developer Check; only admitted `kaori/staging` may cut the next intentional RC.

---

### Task 1: Lock the persistent-vs-release environment contract

**Files:**
- Modify: `tests/contracts/release/test_uat_vps_deployment_contract.py`
- Modify: `tests/contracts/release/test_environment_configuration_contract.py`

**Interfaces:**
- Consumes: current `compose.production.yml`, `.env.production.example`, `deploy/vps/deploy.sh`, `deploy/vps/rollback.sh`, `.github/workflows/deploy-uat-vps.yml`.
- Produces: failing contract assertions requiring release metadata to be absent from persistent env, injected by Compose, passed by workflow/deploy, normalized for application metadata, and preserved for rollback.

- [x] **Step 1: Add RED assertions**

Add assertions that `.env.production.example` does not contain active assignments for `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, or `APP_BUILD_DATE`; that `compose.production.yml` explicitly maps all four variables from deployment environment; that `deploy.sh` requires a third governed release-version argument and normalizes it to no-`v` `APP_VERSION`; that workflow passes `candidate_tag` to `deploy.sh`; and that rollback requires a previous-version state file.

- [x] **Step 2: Run focused RED contract**

Developer Check #188 proved the initial persistent-env boundary RED with `3 failed, 2302 passed`. Developer Check #200 then proved the tag-normalization regression RED while all preceding lint/type/migration gates passed.

- [x] **Step 3: Commit RED authority**

The RED contract is committed on `kaori/task-49-release-env-boundary` and linked to PR #128 / Issue #49.

### Task 2: Inject release identity without mutating persistent env

**Files:**
- Modify: `.env.production.example`
- Modify: `compose.production.yml`
- Modify: `deploy/vps/deploy.sh`
- Modify: `.github/workflows/deploy-uat-vps.yml`

**Interfaces:**
- Consumes: `deploy.sh IMAGE@sha256:<digest> SOURCE_SHA RELEASE_VERSION`, where `RELEASE_VERSION` is the governed Git-tag form.
- Produces: exported `KAORI_IMAGE`, normalized `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` for Compose; all application containers receive those values explicitly.

- [x] **Step 1: Remove release assignments from persistent template**

The production template documents `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` without active assignments and states that governed deployment owns ordinary release identity.

- [x] **Step 2: Make Compose explicit runtime identity authority**

`compose.production.yml` explicitly injects:

```yaml
KAORI_IMAGE: ${KAORI_IMAGE:?KAORI_IMAGE is supplied by governed deployment}
APP_VERSION: ${APP_VERSION:?APP_VERSION is supplied by governed deployment}
APP_BUILD_SHA: ${APP_BUILD_SHA:?APP_BUILD_SHA is supplied by governed deployment}
APP_BUILD_DATE: ${APP_BUILD_DATE:?APP_BUILD_DATE is supplied by governed deployment}
```

This explicit `environment` block overrides any accidental stale value in `env_file`.

- [x] **Step 3: Extend deploy transaction identity**

`deploy.sh` accepts a digest-qualified image, 40-character source SHA, and governed `vX.Y.Z` / `vX.Y.Z-rc.N` release version. After pulling the image and proving `org.opencontainers.image.revision` equals the source SHA, it derives `.Created` and exports:

```bash
app_version="${release_version#v}"
export KAORI_IMAGE="$image"
export APP_VERSION="$app_version"
export APP_BUILD_SHA="$source_sha"
export APP_BUILD_DATE="$image_created"
```

The governed release tag is retained in deployment state for rollback; the application receives canonical SemVer without the Git-tag prefix. No release value is written to `/etc/kaori/.env.production`.

- [x] **Step 4: Pass the governed candidate version from workflow**

`deploy-uat-vps.yml` exposes `REQUESTED_VERSION` from `needs.admission.outputs.candidate_tag`, includes it in the quoted remote payload, and invokes:

```bash
bash "$deploy_script" "$requested_image" "$requested_sha" "$requested_version"
```

- [ ] **Step 5: Run focused GREEN contract**

Require the final Developer Check on the frozen head SHA to pass before staging integration.

### Task 3: Preserve coherent rollback release identity

**Files:**
- Modify: `deploy/vps/deploy.sh`
- Modify: `deploy/vps/rollback.sh`
- Add: `deploy/vps/release-state.sh`
- Modify: `tests/contracts/release/test_uat_vps_deployment_contract.py`

**Interfaces:**
- Consumes: deployment-state `current-version`, `previous-version` alongside image/source records.
- Produces: rollback invocation with previous immutable image, previous source SHA, and previous governed release tag; standalone Compose operations derive no-`v` `APP_VERSION` from state.

- [x] **Step 1: Record current and previous version**

Deployment state copies existing `current-version` to `previous-version`, records the current governed tag in `current-version`, and records image build date alongside image/source evidence.

- [x] **Step 2: Require previous version during rollback**

`rollback.sh` requires and validates `previous-version`, then invokes `deploy.sh` with previous image, source SHA, and governed version. `release-state.sh` derives `APP_VERSION` by stripping the leading `v` whenever standalone backup/restore/verify loads recorded state.

- [ ] **Step 3: Run focused GREEN contract**

Require the final work-branch Developer Check to pass with no release/deployment contract failures.

### Task 4: Align operator documentation and verify release gates

**Files:**
- Modify: `deploy/vps/README.md`
- Modify: `docs/deployment/RELEASE_GOVERNANCE.md`
- Modify: `docs/superpowers/specs/2026-09-02-vps-compose-deployment-design.md`
- Modify: `scripts/verify_release_governance.py`

**Interfaces:**
- Consumes: implemented deployment behavior.
- Produces: operator/release contract stating persistent env is one-time/long-lived, Git tags keep `v`, application `APP_VERSION` omits `v`, and release identity is deployment-managed.

- [x] **Step 1: Update VPS/release documentation**

Documentation separates long-lived host configuration from per-release identity and records the Git-tag-to-application-version normalization contract.

- [ ] **Step 2: Run release-focused verification**

The final Developer Check must provide fresh passing evidence for Workflow Lint, Ruff, DjLint, Code Health, Pyright, Type Safety, Migration Graph, focused contracts/migrations, and frontend formatting. `verify_release_governance.py` must treat `.env.example` as the source/default version contract while proving `.env.production.example` has no active release identity and production Compose/deploy inject release metadata.

- [ ] **Step 3: Run path-aware Developer Check**

Push the final branch SHA and require the repository Developer Check to pass before PR integration to `kaori/staging`.

- [ ] **Step 4: Staging admission and fresh RC**

After PR merge, require Full Admission on the exact new staging SHA. RC `v0.1.0-rc.3` remains historical and must not be deployed because it predates this contract. Cut a fresh intentional RC only from the newly admitted staging SHA, then resume #49 VPS UAT.
