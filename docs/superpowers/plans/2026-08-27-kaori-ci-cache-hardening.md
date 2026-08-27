# KAORI CI Cache and Validation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce repeated CI build/download cost on the self-hosted KAORI runner while preserving full machine validation and eliminating the current static-quality blockers without changing application logic.

**Architecture:** The persistent self-hosted runner reuses a CI toolchain image keyed by immutable toolchain inputs instead of commit SHA, while Docker/BuildKit cache mounts retain package downloads and a dedicated Docker volume retains the Trivy vulnerability database. Every lint, security, test, frontend, image, runtime, migration, and DAST gate still executes on every governed run; only downloads/build layers are cached.

**Tech Stack:** GitHub Actions, Docker/BuildKit, Python 3.12, Node 22, pip, npm, Trivy, Ruff, Pytest, KAORI existing quality gates.

**Spec:** `docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md` section 14 and Governance v1 branch model.

## Global Constraints

- Cache may accelerate immutable/download/build inputs only.
- Never cache or reuse test results, database state, generated test evidence, runtime health results, DAST results, lint results, or vulnerability scan conclusions.
- All governed `kaori/**` branches run full CI.
- No `noqa`, `xfail`, new skip marker, rule suppression, or quality-gate reduction may be introduced solely to get green CI.
- A green workflow is not sufficient if logs contain unexpected application tracebacks, HTTP 5xx, migration/runtime failure, failed assertions, or unexplained skipped tests.
- Production validation image remains source-SHA-specific and must be scanned and runtime-validated on every run.
- Self-hosted runner cache must fail open for performance: if cache is absent/corrupt, rebuild/download normally and continue validation.

---

### Task 1: Lock the Safe-Cache Contract

**Files:**
- Create: `tests/contracts/release/test_github_actions_cache_contract.py`

**Interfaces:**
- Consumes: `.github/workflows/quality.yml`, `.github/ci/Dockerfile`, `Dockerfile`.
- Produces: Regression contract preventing future cache changes from bypassing validation.

- [ ] **Step 1: Write the failing contract**

Create:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / ".github/workflows/quality.yml"
CI_DOCKERFILE = ROOT / ".github/ci/Dockerfile"
PRODUCTION_DOCKERFILE = ROOT / "Dockerfile"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ci_toolchain_is_input_keyed_instead_of_commit_keyed() -> None:
    source = read(QUALITY)
    assert "Resolve CI Toolchain Cache Key" in source
    assert "requirements-security.txt" in source
    assert "requirements/base.txt" in source
    assert "requirements/dev.txt" in source
    assert "kaori-ci-toolchain:${{ github.sha }}" not in source


def test_toolchain_build_reuses_existing_local_image() -> None:
    source = read(QUALITY)
    assert 'docker image inspect "$CI_TOOLCHAIN_IMAGE"' in source
    assert "Reusing cached CI toolchain" in source


def test_cache_does_not_replace_required_validation_jobs() -> None:
    source = read(QUALITY)
    for token in (
        "Run Static Foundation Gate",
        "Run Free-Plan Static Security Gate",
        "Run Functional Test Gate",
        "Build and Verify Frontend",
        "Scan Production Validation Image",
        "Validate Production Runtime",
        "KAORI CI Admission",
    ):
        assert token in source


def test_buildkit_package_cache_mounts_are_present() -> None:
    assert "type=cache,target=/root/.cache/pip" in read(CI_DOCKERFILE)
    production = read(PRODUCTION_DOCKERFILE)
    assert "type=cache,target=/root/.cache/pip" in production
    assert "type=cache,target=/root/.npm" in production


def test_trivy_database_is_cached_but_scan_still_runs() -> None:
    source = read(QUALITY)
    assert "kaori-trivy-cache" in source
    assert "trivy image" in source
    assert "--exit-code 1" in source
```

- [ ] **Step 2: Run and confirm RED**

```bash
pytest -q tests/contracts/release/test_github_actions_cache_contract.py
```

Expected: FAIL because the workflow still keys the CI toolchain by commit SHA and package/security cache mounts are not fully present.

---

### Task 2: Key and Reuse the CI Toolchain by Actual Inputs

**Files:**
- Modify: `.github/workflows/quality.yml`
- Modify: `tests/contracts/release/test_github_actions_cache_contract.py`

**Interfaces:**
- Consumes: Toolchain inputs `.github/ci/Dockerfile`, `.github/ci/requirements-security.txt`, `requirements/base.txt`, `requirements/dev.txt`.
- Produces: Stable local image name `kaori-ci-toolchain:<20-char-input-hash>` reusable across source-only commits.

- [ ] **Step 1: Remove commit-SHA toolchain environment**

Delete the workflow-level line:

```yaml
CI_TOOLCHAIN_IMAGE: kaori-ci-toolchain:${{ github.sha }}
```

Do not change `VALIDATION_IMAGE=kaori:ci-${GITHUB_SHA}`; the production validation image must remain commit-specific.

- [ ] **Step 2: Add `Resolve CI Toolchain Cache Key` after each checkout**

Use exactly:

```yaml
- name: Resolve CI Toolchain Cache Key
  shell: bash
  run: |
    set -Eeuo pipefail
    CI_TOOLCHAIN_KEY="$(cat \
      .github/ci/Dockerfile \
      .github/ci/requirements-security.txt \
      requirements/base.txt \
      requirements/dev.txt \
      | sha256sum | cut -c1-20)"
    echo "CI_TOOLCHAIN_KEY=$CI_TOOLCHAIN_KEY" >> "$GITHUB_ENV"
    echo "CI_TOOLCHAIN_IMAGE=kaori-ci-toolchain:$CI_TOOLCHAIN_KEY" >> "$GITHUB_ENV"
```

Add it to every job that uses `CI_TOOLCHAIN_IMAGE`: static quality, static security, functional tests, frontend, and production runtime.

- [ ] **Step 3: Replace each unconditional toolchain build**

Use exactly:

```yaml
- name: Build or Reuse CI Toolchain
  shell: bash
  run: |
    set -Eeuo pipefail
    if docker image inspect "$CI_TOOLCHAIN_IMAGE" >/dev/null 2>&1; then
      echo "Reusing cached CI toolchain: $CI_TOOLCHAIN_IMAGE"
      exit 0
    fi
    docker build \
      --file .github/ci/Dockerfile \
      --tag "$CI_TOOLCHAIN_IMAGE" \
      .
```

This cache is local to the persistent self-hosted runner. A miss executes the normal build.

- [ ] **Step 4: Run the cache contract**

```bash
pytest -q tests/contracts/release/test_github_actions_cache_contract.py
```

Expected: remaining failures only for package-cache and Trivy steps.

- [ ] **Step 5: Commit the isolated toolchain-key change**

```bash
git add .github/workflows/quality.yml tests/contracts/release/test_github_actions_cache_contract.py
git commit -m "perf(ci): reuse toolchain by immutable inputs"
```

---

### Task 3: Add BuildKit Download Caches Without Polluting Images

**Files:**
- Modify: `.github/ci/Dockerfile`
- Modify: `Dockerfile`

**Interfaces:**
- Consumes: Docker BuildKit already enabled by the Dockerfile syntax directive.
- Produces: Persistent pip/npm download caches stored outside committed image layers.

- [ ] **Step 1: Add pip cache mount to CI toolchain dependency install**

Replace:

```dockerfile
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/kaori-requirements/dev.txt \
    && python -m pip install -r /tmp/requirements-security.txt
```

with:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_NO_CACHE_DIR=0 python -m pip install --upgrade pip \
    && PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/kaori-requirements/dev.txt \
    && PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/requirements-security.txt
```

The cache mount is external to the final image layer, so enabling pip caching for this RUN does not leave wheel caches in the image.

- [ ] **Step 2: Add pip cache mount to production base dependency install**

Replace the production Dockerfile base install with:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_NO_CACHE_DIR=0 python -m pip install --upgrade pip \
    && PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/requirements/base.txt
```

Keep the global `PIP_NO_CACHE_DIR=1` environment for runtime behavior; the RUN-local override exists only to populate/reuse the BuildKit cache mount.

- [ ] **Step 3: Add pip cache mount to development dependency install**

Use:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    PIP_NO_CACHE_DIR=0 python -m pip install -r /tmp/requirements/dev.txt
```

- [ ] **Step 4: Add npm cache mount to frontend build**

Replace:

```dockerfile
RUN npm ci
```

with:

```dockerfile
RUN --mount=type=cache,target=/root/.npm npm ci
```

`npm ci` must still execute every time its layer is invalidated; only registry downloads are cached.

- [ ] **Step 5: Run Dockerfile/static contracts**

```bash
pytest -q tests/contracts/release/test_github_actions_cache_contract.py
bash scripts/quality_gate.sh --static
```

Expected: cache contract now fails only until Trivy cache is implemented; existing Dockerfile lint must remain healthy.

- [ ] **Step 6: Commit**

```bash
git add .github/ci/Dockerfile Dockerfile
git commit -m "perf(build): cache pip and npm downloads with BuildKit"
```

---

### Task 4: Persist the Trivy Vulnerability Database, Not Scan Results

**Files:**
- Modify: `.github/workflows/quality.yml`

**Interfaces:**
- Consumes: `trivy image` invocation in production-runtime job.
- Produces: Docker volume `kaori-trivy-cache` containing Trivy database/cache across jobs/runs while every image is scanned afresh.

- [ ] **Step 1: Create/reuse cache volume before scan**

Add immediately before `Scan Production Validation Image`:

```yaml
- name: Prepare Trivy Database Cache
  run: docker volume create kaori-trivy-cache >/dev/null
```

Docker volume creation is idempotent.

- [ ] **Step 2: Mount cache volume into Trivy**

Use:

```yaml
- name: Scan Production Validation Image
  run: >-
    docker run --rm
    --volume /var/run/docker.sock:/var/run/docker.sock
    --volume kaori-trivy-cache:/root/.cache/trivy
    "$CI_TOOLCHAIN_IMAGE"
    trivy image
    --exit-code 1
    --ignore-unfixed
    --severity HIGH,CRITICAL
    --scanners vuln
    "$VALIDATION_IMAGE"
```

Do not add `--skip-db-update`; Trivy remains responsible for freshness and may update the cached DB when required.

- [ ] **Step 3: Run the cache contract and static gate**

```bash
pytest -q tests/contracts/release/test_github_actions_cache_contract.py
bash scripts/quality_gate.sh --static
```

Expected: PASS unless a pre-existing static source failure remains.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/quality.yml
git commit -m "perf(security): persist Trivy database cache"
```

---

### Task 5: Clear the Current Ruff Blockers Without Logic Changes

**Files:**
- Modify: `app/reports/export/xlsx/analytics_profiles.py`
- Modify: `app/reports/export/xlsx/builder.py`
- Modify: `app/reports/storage/service.py`
- Modify: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Consumes: Latest real self-hosted static-job logs.
- Produces: Ruff-clean source with import-only changes and unchanged runtime behavior.

- [ ] **Step 1: Refresh the latest static job log before editing**

Fetch the newest `KAORI CI` run for the active branch and confirm whether these four findings remain. If a newer failure differs, stop this task and follow systematic debugging on the newer evidence before editing.

Known evidence from run #16 was:

```text
analytics_profiles.py        UP035 Callable import
builder.py                   I001 import ordering
app/reports/storage/service.py I001 import ordering
tests/reports/test_analytics_xlsx_standard.py I001 import ordering
```

- [ ] **Step 2: Fix `analytics_profiles.py` imports**

Use:

```python
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any
```

Do not change any function or data behavior.

- [ ] **Step 3: Fix `builder.py` import order**

Order the app imports so the `tabular` import block comes before `xlsx.overview`:

```python
from app.reports.export.tabular import (
    TABULAR_EXPORT_STANDARD,
    TABULAR_SCHEMA_VERSION,
    protect_spreadsheet_formula,
    serialize_tabular_value,
)
from app.reports.export.xlsx.overview import build_inventory_overview_sheet
```

Keep the remaining `xlsx.standard` and `xlsx.style` imports after `xlsx.overview`.

- [ ] **Step 4: Fix `app/reports/storage/service.py` import order**

Place:

```python
from app.reports.storage import verification as storage_check
```

before:

```python
from app.reports.storage.health import (
```

Do not change service behavior.

- [ ] **Step 5: Fix test import order**

At the third-party import boundary use:

```python
import pytest
from openpyxl import load_workbook
```

- [ ] **Step 6: Run targeted lint and report tests**

```bash
ruff check \
  app/reports/export/xlsx/analytics_profiles.py \
  app/reports/export/xlsx/builder.py \
  app/reports/storage/service.py \
  tests/reports/test_analytics_xlsx_standard.py
pytest -q tests/reports/test_analytics_xlsx_standard.py
```

Expected: PASS.

- [ ] **Step 7: Run full static gate**

```bash
bash scripts/quality_gate.sh --static
```

Expected: PASS. If another failure appears, treat it as new evidence and debug it rather than suppressing it.

- [ ] **Step 8: Commit**

```bash
git add \
  app/reports/export/xlsx/analytics_profiles.py \
  app/reports/export/xlsx/builder.py \
  app/reports/storage/service.py \
  tests/reports/test_analytics_xlsx_standard.py
git commit -m "fix(quality): clear current Ruff blockers"
```

---

### Task 6: Prove Full Validation Still Executes and Cache Actually Helps

**Files:**
- No source changes unless a real CI defect is identified.

**Interfaces:**
- Consumes: Cache-hardened workflow and static-clean source.
- Produces: Full CI evidence plus cache-hit evidence.

- [ ] **Step 1: Push the issue-linked CI chore branch**

The branch must match `kaori/**` so full CI triggers.

- [ ] **Step 2: Require every job to succeed**

Required jobs:

```text
Static, Architecture, and Governance
Secrets, SAST, Dependencies, and Workflow Security
Functional and Integration Tests
Frontend Reproducibility
Production Image, Container Security, Runtime, and DAST
KAORI CI Admission
```

- [ ] **Step 3: Inspect logs semantically**

Review logs for unexpected occurrences of:

```text
Traceback
AssertionError
FAILED
ERROR
HTTP 500
HTTP 502
HTTP 503
HTTP 504
migration failed
connection refused
unexpected skip
```

Interpret in context; scanner output may contain the word `ERROR` without representing an application error.

- [ ] **Step 4: Prove toolchain reuse**

On a subsequent source-only commit or a rerun with identical toolchain inputs, the relevant jobs must log:

```text
Reusing cached CI toolchain: kaori-ci-toolchain:<input-hash>
```

while still executing static, security, functional, frontend, production-image, runtime, DAST, and admission commands.

- [ ] **Step 5: Prove Trivy DB reuse without scan bypass**

Confirm Trivy does not need a cold database download on every run when its cache is current, and confirm `trivy image ... --exit-code 1` executes on each production validation image.

- [ ] **Step 6: Treat every real failure as a new debugging cycle**

Fetch failed job logs, identify root cause, reproduce with the same command, apply the minimum fix, run targeted verification, then rerun full CI. Do not batch unrelated speculative fixes.

---

### Task 7: Integrate CI Hardening into `kaori/staging` for UAT

**Files:**
- No additional source files unless staging CI or UAT exposes a defect.

**Interfaces:**
- Consumes: Fully green CI-hardening branch.
- Produces: Cache-hardened staging increment for local UAT.

- [ ] **Step 1: Integrate the green branch into `kaori/staging`**

Preserve commit history. Do not promote directly to `main`.

- [ ] **Step 2: Require full staging CI**

All six required jobs in Task 6 must succeed on the exact staging integration SHA.

- [ ] **Step 3: Local UAT**

The user syncs:

```bash
git fetch origin
git switch kaori/staging || git switch --track -c kaori/staging origin/kaori/staging
git pull --ff-only origin kaori/staging
```

Validate Dev Container startup, frontend reproducibility, representative Reports behavior touched by the Ruff-clean files, application navigation, and compose/worker lifecycle. Record explicit acceptance or rejection in the linked CI Chore Issue.

- [ ] **Step 4: Do not mark the Chore Done before UAT approval**

Green CI moves the work to `Staging`/`UAT`; only explicit local acceptance moves it to `Done`.
