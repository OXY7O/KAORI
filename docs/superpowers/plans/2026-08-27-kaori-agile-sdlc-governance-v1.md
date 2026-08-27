# KAORI Agile SDLC Governance v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement KAORI Agile SDLC Governance v1 as a professional, versioned application-delivery baseline spanning GitHub Issues, repository templates, branch/CI behavior, GitHub Project configuration, staging/UAT promotion, branch hygiene, and traceable release readiness.

**Architecture:** `main` and `kaori/staging` are the only default long-lived branches. Governed work is represented by GitHub Issues and temporary issue-linked branches; full CI precedes integration to `kaori/staging`; local UAT is the human acceptance authority; accepted staging increments are promoted to `main` by explicit PR and merge commit. Repository-controlled templates and documentation define the portable contract, while GitHub Project fields/views provide the operational board. Platform Governance / Platform Workflow standards may later supersede duplicated rules through explicit convergence.

**Tech Stack:** GitHub Issues, GitHub Projects, GitHub Actions, YAML Issue Forms, Markdown, Bash, Docker/BuildKit, self-hosted GitHub Actions runner, Ruff/djLint/Pyright/Pytest/Prettier, KAORI existing quality gates.

**Spec:** `docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md`

## Global Constraints

- Governance version is `1.0` until a separately approved governance change increments it.
- `main` = production-ready baseline and release authority.
- `kaori/staging` = permanent integration and local-UAT authority.
- `main` and `kaori/staging` are the only default long-lived branches.
- `kaori/working` is retired after all required commits are represented in `kaori/staging`.
- Temporary branches are deleted after integration when no longer needed.
- Default sprint cadence = two weeks, explicitly flexible.
- `Done` requires explicit local UAT approval from `kaori/staging`.
- Full KAORI CI precedes staging integration and release promotion.
- Merge strategy to `main` = merge commit.
- GitHub Project Iteration = sprint authority; GitHub Milestone = release-target authority.
- CI caching may accelerate immutable/download/build inputs but must never bypass source lint, type checks, tests, migration validation, runtime checks, frontend reproducibility, image scanning, or DAST.
- Existing quality/security rules must not be weakened to make governance changes pass.
- PR creation and merge into `main` remain explicit human-controlled gates.
- Current GitHub connector can manage repository files, Issues, branches, PRs, and Actions evidence, but does not expose creation of repository labels or GitHub Project custom fields/views. Those one-time metadata steps must therefore be performed through GitHub UI (or later migrated to platform-level automation) and are documented exactly below.

---

### Task 1: Lock Governance v1 and Branch Authority

**Files:**
- Modify: `docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md`
- Create: `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- Test: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: Governance v1 design decisions approved on 2026-08-27.
- Produces: Canonical application-local delivery contract used by Issue Forms, PR template, CI trigger rules, and future Platform Governance convergence.

- [ ] **Step 1: Write the failing governance contract test**

Create `tests/contracts/release/test_kaori_delivery_governance_contract.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md"
WORKFLOW = ROOT / "docs/engineering/KAORI_DELIVERY_WORKFLOW.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_governance_v1_locks_long_lived_branches_and_uat_authority() -> None:
    design = read(DESIGN)
    workflow = read(WORKFLOW)

    for source in (design, workflow):
        assert "main" in source
        assert "kaori/staging" in source
        assert "local UAT" in source or "Local UAT" in source
        assert "merge commit" in source.casefold()
        assert "two-week" in source

    assert "only two branches are long-lived" in design.casefold()
    assert "kaori/working" in design
    assert "retired" in design.casefold()
    assert "Done" in workflow
    assert "UAT" in workflow


def test_delivery_workflow_separates_sprint_from_release_authority() -> None:
    workflow = read(WORKFLOW)
    assert "Iteration" in workflow
    assert "Milestone" in workflow
    assert "Sprint" in workflow
    assert "Release" in workflow
```

- [ ] **Step 2: Run the contract test and confirm RED**

Run:

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
```

Expected: FAIL because `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` does not yet exist.

- [ ] **Step 3: Create the canonical delivery workflow document**

Create `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` with this minimum structure and exact authority statements:

```markdown
# KAORI Application Delivery Workflow

**Governance Version:** 1.0
**Scope:** KAORI application repository
**Authority:** Application-local baseline
**Future Authority:** Platform Governance / Platform Workflow standards when formally adopted

## Branch Authority

Only two branches are long-lived by default:

- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and local UAT authority.

`kaori/working` is retired after migration. Temporary work branches are deleted after their changes are integrated and no longer needed.

## Delivery Path

`Backlog -> Ready -> issue-linked branch -> full CI -> kaori/staging -> full staging CI -> Local UAT -> accepted -> PR to main -> merge commit -> main`

## Sprint and Release

- GitHub Project **Iteration** is the Sprint authority.
- Default Sprint cadence is two-week and flexible.
- GitHub **Milestone** is the Release authority.
- Sprint completion never forces a release.

## Definition of Done

A work item is not Done merely because code or CI is complete. It remains in UAT until local UAT from `kaori/staging` is explicitly approved.

## Branch Hygiene

Merged temporary branches are deleted after no active work depends on them. Stale branches are not retained as an audit mechanism; Issues, PRs, commits, releases, and governance records provide the durable evidence.
```

Expand the document with the complete lifecycle, Issue hierarchy, branch naming, hotfix path, failure return paths, UAT evidence, release promotion, and future convergence described by the spec. Do not introduce additional long-lived branches.

- [ ] **Step 4: Run the contract test and existing static governance gate**

Run:

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
bash scripts/quality_gate.sh --static
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md \
  docs/engineering/KAORI_DELIVERY_WORKFLOW.md \
  tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "docs(governance): lock KAORI delivery workflow v1"
```

---

### Task 2: Add Professional GitHub Issue Forms and PR Evidence Contract

**Files:**
- Create: `.github/ISSUE_TEMPLATE/epic.yml`
- Create: `.github/ISSUE_TEMPLATE/user-story.yml`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/task.yml`
- Create: `.github/ISSUE_TEMPLATE/spike.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: Governance v1 work-item contracts and Definition of Ready/Done.
- Produces: Structured intake for Epic, User Story, Bug, Task, Spike, plus PR evidence required for staging/main promotion.

- [ ] **Step 1: Extend the governance contract test and confirm RED**

Append:

```python
import yaml

ISSUE_TEMPLATE_DIR = ROOT / ".github/ISSUE_TEMPLATE"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((ISSUE_TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def test_issue_forms_cover_governed_work_types() -> None:
    required = {
        "epic.yml": "Epic",
        "user-story.yml": "User Story",
        "bug.yml": "Bug",
        "task.yml": "Task",
        "spike.yml": "Spike",
    }
    for filename, expected_name in required.items():
        form = load_yaml(filename)
        assert expected_name in form["name"]
        assert form["body"]
        assert any(item.get("type") == "textarea" for item in form["body"])


def test_pull_request_template_requires_traceable_evidence() -> None:
    source = read(ROOT / ".github/PULL_REQUEST_TEMPLATE.md")
    for token in (
        "Linked Issue",
        "Acceptance Criteria",
        "Test Evidence",
        "Security",
        "Migration",
        "UAT",
        "Release Impact",
    ):
        assert token in source
```

Run:

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
```

Expected: FAIL because templates do not yet exist.

- [ ] **Step 2: Create `epic.yml`**

Use GitHub Issue Form fields for Outcome, Problem Statement, Business/Operational Value, Scope, Out of Scope, Success Metrics, Risks, Dependencies, and Exit Criteria. Title prefix must be `[EPIC] `. Do not encode Project lifecycle status as a label.

Minimum header:

```yaml
name: Epic
description: Define a multi-story KAORI product or platform outcome.
title: "[EPIC] "
body:
  - type: markdown
    attributes:
      value: |
        Use this form for a governed outcome that requires multiple child work items.
```

- [ ] **Step 3: Create `user-story.yml`**

Use fields for Persona, Capability, Outcome, Acceptance Criteria, Definition of Ready evidence, Technical Notes, Security, Data/Migration, Observability, Test Strategy, Dependencies, and UAT Evidence. Title prefix: `[STORY] `.

Acceptance Criteria guidance must explicitly request Given/When/Then where practical.

- [ ] **Step 4: Create `bug.yml`**

Use fields for Observed Behavior, Expected Behavior, Reproduction, Impact, Root Cause status/evidence, Regression Test, Security/Data impact, and UAT Evidence. Title prefix: `[BUG] `.

Do not let the form suggest suppressing tests or bypassing root-cause analysis.

- [ ] **Step 5: Create `task.yml` and `spike.yml`**

`task.yml` must capture parent work item, deliverable, completion criteria, dependencies, and verification. `spike.yml` must capture Question, Hypothesis, Timebox, Evidence, Decision, and Follow-up Stories/Tasks. Title prefixes: `[TASK] ` and `[SPIKE] `.

- [ ] **Step 6: Create `config.yml`**

Use:

```yaml
blank_issues_enabled: false
contact_links: []
```

This keeps intake governed through defined forms.

- [ ] **Step 7: Create `.github/PULL_REQUEST_TEMPLATE.md`**

Required sections:

```markdown
## Linked Issue

Closes/Relates to #

## Scope Summary

## Acceptance Criteria Coverage

## Test Evidence

## Security Impact

## Migration / Data Impact

## Observability / Operational Impact

## UAT

- [ ] Not yet applicable — work branch PR/integration
- [ ] `kaori/staging` local UAT passed

## Release Impact

## Reviewer Checklist

- [ ] Change matches linked work item.
- [ ] Required CI is green without suppressed failures.
- [ ] No unexpected skipped tests, tracebacks, HTTP 5xx, or migration/runtime failures remain.
- [ ] Generated frontend artifacts are reproducible when applicable.
- [ ] Documentation/contracts are aligned.
```

- [ ] **Step 8: Verify**

Run:

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
bash scripts/quality_gate.sh --static
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add .github/ISSUE_TEMPLATE .github/PULL_REQUEST_TEMPLATE.md tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "feat(governance): add governed issue and PR templates"
```

---

### Task 3: Configure the KAORI GitHub Project Operating Model

**Files:**
- Create: `docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md`
- Modify: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: GitHub Project named `KAORI` already created by the user.
- Produces: Exact one-time Project configuration that operationalizes Governance v1.

- [ ] **Step 1: Add a contract for the Project setup guide and confirm RED**

Append:

```python

def test_project_setup_guide_defines_canonical_fields_and_views() -> None:
    source = read(ROOT / "docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md")
    for token in (
        "Backlog",
        "Refinement",
        "Ready",
        "In Progress",
        "Code Review / CI",
        "Staging",
        "UAT",
        "Blocked",
        "Done",
        "P0 — Critical",
        "P1 — High",
        "P2 — Medium",
        "P3 — Low",
        "1, 2, 3, 5, 8, 13",
        "Product Backlog",
        "Current Sprint",
        "Staging & UAT",
        "Release Readiness",
    ):
        assert token in source
```

Run the targeted test; expect FAIL because the guide does not exist.

- [ ] **Step 2: Document exact Project fields**

Create `docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md` and configure the Project UI exactly as follows:

```text
Project: KAORI

Status (single select):
Backlog
Refinement
Ready
In Progress
Code Review / CI
Staging
UAT
Blocked
Done

Type (single select):
Epic
User Story
Bug
Task
Spike
Chore
Technical Debt

Priority (single select):
P0 — Critical
P1 — High
P2 — Medium
P3 — Low

Story Points (number):
Allowed planning scale: 1, 2, 3, 5, 8, 13

Iteration:
Name: Sprint
Duration: 2 weeks
Flexible carry-over allowed

Release Target:
Do not duplicate Milestone; use repository Milestone as release authority.
```

- [ ] **Step 3: Document exact Project views**

Define:

```text
Product Backlog      -> Status = Backlog/Refinement/Ready, grouped by Priority
Current Sprint       -> Iteration = current, grouped by Status
Active Delivery      -> Status = In Progress/Code Review / CI/Blocked
Staging & UAT        -> Status = Staging/UAT/Blocked
Epics / Roadmap      -> Type = Epic
Bugs & Incidents     -> Type = Bug, grouped by Priority
Release Readiness    -> Milestone is set, Status != Done or current accepted increment
```

- [ ] **Step 4: Document Project automation rules**

Use GitHub Project built-in workflows where available:

```text
Newly added item      -> Backlog
Issue reopened        -> Backlog (or prior active state if intentionally restored)
Issue closed          -> do not auto-mark Done unless UAT evidence is present
PR opened             -> Code Review / CI for linked work where appropriate
PR merged to staging  -> Staging, then UAT after staging CI success
```

Do not enable an automation that turns `closed` into `Done` unconditionally; Governance v1 requires explicit UAT acceptance.

- [ ] **Step 5: Apply the one-time Project configuration in GitHub UI**

Because the current connector does not expose GitHub Projects write APIs, apply the documented field/view configuration through GitHub Project **KAORI** UI. Treat the checked-in guide as authority and evidence for later Platform Governance automation.

- [ ] **Step 6: Verify documentation contract**

Run:

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "docs(governance): define KAORI project operating model"
```

---

### Task 4: Establish the Professional Label Taxonomy

**Files:**
- Create: `docs/engineering/KAORI_GITHUB_LABELS.md`
- Modify: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: Governance v1 label model.
- Produces: Exact repository label catalog used by Issues/PRs without duplicating Project Status.

- [ ] **Step 1: Add a label-catalog contract and confirm RED**

Append:

```python

def test_label_catalog_is_portable_and_does_not_duplicate_status() -> None:
    source = read(ROOT / "docs/engineering/KAORI_GITHUB_LABELS.md")
    for token in (
        "type:epic",
        "type:story",
        "type:bug",
        "priority:p0-critical",
        "priority:p3-low",
        "area:ci-cd",
        "area:security",
        "impact:migration",
        "workflow:blocked",
        "workflow:expedite",
    ):
        assert token in source
    assert "status:in-progress" not in source
    assert "status:done" not in source
```

Run targeted test; expect FAIL because the label catalog does not exist.

- [ ] **Step 2: Create the label catalog**

Create `docs/engineering/KAORI_GITHUB_LABELS.md` with label name, description, and a stable color. Use this baseline:

```text
type:epic               5319E7  Multi-story product/platform outcome
type:story              7C3AED  User-visible or operational capability
type:bug                D73A4A  Defect or regression
type:task               1D76DB  Concrete implementation/operational task
type:spike              8250DF  Timeboxed research/decision work
type:chore              6B7280  Maintenance/administrative work
type:tech-debt          B45309  Explicit technical debt

priority:p0-critical    B91C1C  Immediate critical impact
priority:p1-high        DC2626  High priority
priority:p2-medium      D97706  Normal planned priority
priority:p3-low         64748B  Lower priority

area:frontend           7C3AED  Frontend/UI
a rea:backend           2563EB  Backend/application services
area:reports            0891B2  Reports and publication
area:intelligence       9333EA  Intelligence domain
area:kubernetes         326CE5  Kubernetes domain
area:object-storage     0F766E  Object Storage domain
area:analytics          4F46E5  Analytics domain
area:integrations       0284C7  Integration providers
area:settings           475569  Settings/identity/access
area:platform           334155  Application platform/foundation
area:ci-cd              0369A1  CI/CD and delivery automation
area:security           BE123C  Security-related implementation
area:observability      0E7490  Monitoring/observability

impact:breaking         991B1B  Breaking contract/change
impact:migration        C2410C  Schema/data/migration impact
impact:security         BE123C  Security impact
impact:performance      0F766E  Performance impact
impact:accessibility    6D28D9  Accessibility impact

workflow:blocked        111827  Work cannot progress
workflow:expedite       E11D48  Approved expedite/hotfix lane
```

Correct the accidental `a rea:backend` spacing in the final file to `area:backend`. Do not add lifecycle-state labels.

- [ ] **Step 3: Create labels in repository Settings**

The current connector cannot create repository label definitions. Create/update the catalog through **Repository Settings -> Issues -> Labels** (or a future Platform Governance automation) using the exact names/descriptions/colors in the checked-in catalog. Existing GitHub default labels may remain only when they do not conflict; remove/rename conflicting duplicates during this one-time cleanup.

- [ ] **Step 4: Verify contract**

Run:

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/KAORI_GITHUB_LABELS.md tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "docs(governance): define professional KAORI label taxonomy"
```

---

### Task 5: Make CI Follow the New Branch Model and Maximize Safe Caching

**Files:**
- Modify: `.github/workflows/quality.yml`
- Modify: `.github/ci/Dockerfile`
- Modify: `.github/ci/run-security-static.sh`
- Modify: `Dockerfile`
- Create or modify: `tests/contracts/release/test_github_actions_governance_contract.py`

**Interfaces:**
- Consumes: `kaori/staging` branch authority, issue-linked `kaori/**` branches, existing self-hosted runner and KAORI full quality pipeline.
- Produces: Full CI on all governed KAORI branches with reusable toolchain/dependency/security caches that cannot bypass logic validation.

- [ ] **Step 1: Write branch/cache contract tests and confirm RED**

Create `tests/contracts/release/test_github_actions_governance_contract.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / ".github/workflows/quality.yml"
CI_DOCKERFILE = ROOT / ".github/ci/Dockerfile"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_quality_workflow_targets_staging_and_governed_kaori_branches() -> None:
    source = read(QUALITY)
    assert "kaori/staging" in source
    assert '"kaori/**"' in source or "'kaori/**'" in source
    assert "kaori/working" not in source
    assert "main" in source


def test_ci_toolchain_cache_is_input_keyed_not_commit_keyed() -> None:
    source = read(QUALITY)
    assert "CI_TOOLCHAIN_KEY" in source
    assert "requirements-security.txt" in source
    assert "CI_TOOLCHAIN_IMAGE: kaori-ci-toolchain:${{ github.sha }}" not in source


def test_ci_cache_does_not_replace_full_validation_gates() -> None:
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
```

Run:

```bash
pytest -q tests/contracts/release/test_github_actions_governance_contract.py
```

Expected: FAIL because the workflow still targets `kaori/working` and the toolchain image is keyed by commit SHA.

- [ ] **Step 2: Change CI trigger authority**

In `.github/workflows/quality.yml`, replace the working-branch trigger with governed KAORI branches:

```yaml
push:
  branches:
    - "kaori/**"
    - main
    - "release/**"
```

Retain PR-to-main validation. Do not use broad `paths-ignore` for application changes in Governance v1.

- [ ] **Step 3: Compute an input-derived CI toolchain key once per job**

Before `Build CI Toolchain`, compute a deterministic key from toolchain inputs:

```bash
CI_TOOLCHAIN_KEY="$(cat \
  .github/ci/Dockerfile \
  .github/ci/requirements-security.txt \
  requirements/base.txt \
  requirements/dev.txt \
  | sha256sum | cut -c1-20)"
echo "CI_TOOLCHAIN_KEY=$CI_TOOLCHAIN_KEY" >> "$GITHUB_ENV"
echo "CI_TOOLCHAIN_IMAGE=kaori-ci-toolchain:$CI_TOOLCHAIN_KEY" >> "$GITHUB_ENV"
```

Remove the workflow-level `CI_TOOLCHAIN_IMAGE: kaori-ci-toolchain:${{ github.sha }}` contract.

Each job may recompute the key cheaply; the resulting image name is stable across commits until toolchain inputs change.

- [ ] **Step 4: Reuse the local self-hosted toolchain image before rebuilding**

Use:

```bash
if docker image inspect "$CI_TOOLCHAIN_IMAGE" >/dev/null 2>&1; then
  echo "Reusing $CI_TOOLCHAIN_IMAGE"
else
  docker build \
    --file .github/ci/Dockerfile \
    --tag "$CI_TOOLCHAIN_IMAGE" \
    .
fi
```

This prevents re-running apt/pip/security-tool downloads for source-only commits on the persistent runner.

- [ ] **Step 5: Add BuildKit cache mounts for package downloads**

In `.github/ci/Dockerfile`, remove `PIP_NO_CACHE_DIR=1` from the CI toolchain image and use Dockerfile cache mounts:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/kaori-requirements/dev.txt \
    && python -m pip install -r /tmp/requirements-security.txt
```

Keep the final image deterministic through pinned requirements and checksum-verified external binaries. Do not cache repository source or test outputs.

For the production Dockerfile, use cache mounts on dependency-install steps while retaining the existing dependency-file-first layer structure:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements/base.txt
```

and for frontend:

```dockerfile
RUN --mount=type=cache,target=/root/.npm npm ci
```

- [ ] **Step 6: Persist Trivy DB without persisting scan results**

Mount a runner-local Docker volume or stable runner path as Trivy cache, e.g.:

```bash
docker volume create kaori-trivy-cache >/dev/null

docker run --rm \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  --volume kaori-trivy-cache:/root/.cache/trivy \
  "$CI_TOOLCHAIN_IMAGE" \
  trivy image \
  --exit-code 1 \
  --ignore-unfixed \
  --severity HIGH,CRITICAL \
  --scanners vuln \
  "$VALIDATION_IMAGE"
```

The vulnerability database may be cached; the image scan itself must run every time.

- [ ] **Step 7: Keep security dependency audits live**

Do not cache or skip `pip-audit`, `npm audit`, Bandit, Semgrep, Gitleaks, actionlint, Zizmor, ShellCheck, or Hadolint results. `run-security-static.sh` must execute each scanner on every governed CI run. Package-manager download caches may accelerate network access without suppressing scanning.

- [ ] **Step 8: Run static and workflow contracts**

Run:

```bash
pytest -q \
  tests/contracts/release/test_github_actions_governance_contract.py \
  tests/contracts/release/test_kaori_delivery_governance_contract.py
bash scripts/quality_gate.sh --static
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add \
  .github/workflows/quality.yml \
  .github/ci/Dockerfile \
  .github/ci/run-security-static.sh \
  Dockerfile \
  tests/contracts/release/test_github_actions_governance_contract.py
git commit -m "perf(ci): cache immutable KAORI toolchain inputs"
```

---

### Task 6: Bootstrap Governed Work Items in GitHub Issues

**Files:**
- No application-code file required.
- Issue bodies are durable governance records.

**Interfaces:**
- Consumes: Professional Issue Forms, label taxonomy, Project fields.
- Produces: First governed Epic and implementation items for Governance v1 and current CI hardening.

- [ ] **Step 1: Create Governance v1 Epic**

Create Issue:

```text
Title: [EPIC] Establish KAORI Agile SDLC Governance v1
Type: Epic
Priority: P1 — High
Area: area:platform, area:ci-cd
Status: In Progress

Outcome:
KAORI has a professional, versioned, application-local work-management and SDLC baseline that can later converge with Platform Governance / Platform Workflow standards.

Exit Criteria:
- Issue Forms and PR template are active.
- Project fields/views match Governance v1.
- label taxonomy is active.
- `kaori/staging` is the UAT branch.
- CI runs on governed `kaori/**` branches.
- staging full CI is green.
- local UAT is explicitly accepted before Done.
- `kaori/working` and merged temporary migration branches are retired when safe.
```

- [ ] **Step 2: Create child Story/Task items**

Create governed work items for:

```text
[STORY] Standardize KAORI issue and pull-request intake
[TASK] Configure KAORI GitHub Project fields and views
[CHORE] Optimize self-hosted CI caching without reducing validation
[TASK] Retire kaori/working after staging migration
```

Link them to the Epic using native sub-issues where available; otherwise reference the Epic explicitly in each body until native hierarchy can be configured.

- [ ] **Step 3: Assign metadata**

Apply Type, Priority, Area, Iteration, Story Points, and Status through the Project and labels according to Governance v1. Do not mark any item Done before staging UAT.

- [ ] **Step 4: Record branch mapping**

For each implementation item, add the branch name to its Issue once branch work begins, using:

```text
kaori/story-<issue>-<slug>
kaori/task-<issue>-<slug>
kaori/chore-<issue>-<slug>
```

- [ ] **Step 5: Verify traceability**

Confirm every active implementation branch has a linked Issue and every Issue moving to Code Review / CI references its branch/commit or PR evidence.

---

### Task 7: Resolve Existing Static Failures Without Weakening Rules

**Files:**
- Modify only files identified by the latest real self-hosted runner logs.
- Current known candidates from run evidence include:
  - `app/reports/export/xlsx/analytics_profiles.py`
  - `app/reports/export/xlsx/builder.py`
  - `app/reports/storage/service.py`
  - `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Consumes: Latest `KAORI CI` failed-job logs from the current staging lineage.
- Produces: Static gate green with no `noqa`, rule suppression, skipped verification, or unrelated refactor.

- [ ] **Step 1: Re-fetch the latest failed static job logs**

Use the latest Actions run for the active implementation branch. Confirm the exact current failures before changing source; do not rely on stale run #16 if newer commits exist.

- [ ] **Step 2: Write/retain regression evidence**

For behavioral code changes, create a focused test before modifying behavior. For purely formatter/import-order findings, use Ruff's canonical fix behavior and preserve all runtime semantics.

- [ ] **Step 3: Apply minimal root-cause fixes**

Examples for previously observed findings:

```python
# analytics_profiles.py
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any
```

For import-order-only failures in `builder.py`, `service.py`, and `test_analytics_xlsx_standard.py`, use the ordering that `ruff check --fix` would produce without changing runtime logic.

- [ ] **Step 4: Run targeted lint and tests**

Run:

```bash
ruff check \
  app/reports/export/xlsx/analytics_profiles.py \
  app/reports/export/xlsx/builder.py \
  app/reports/storage/service.py \
  tests/reports/test_analytics_xlsx_standard.py

pytest -q tests/reports/test_analytics_xlsx_standard.py
```

Expected: PASS.

- [ ] **Step 5: Run full static gate**

```bash
bash scripts/quality_gate.sh --static
```

Expected: PASS with no hidden suppression.

- [ ] **Step 6: Commit**

```bash
git add <only-files-actually-changed>
git commit -m "fix(quality): clear current KAORI static blockers"
```

---

### Task 8: Run Full Machine Verification and Semantically Inspect Logs

**Files:**
- No source changes unless a real failure is diagnosed.

**Interfaces:**
- Consumes: Governance implementation branch and self-hosted CI.
- Produces: Evidence that every required machine gate passes and no log-level logic error is being hidden by a green result.

- [ ] **Step 1: Push governed implementation branch**

Push the active issue-linked/governance branch. Confirm `KAORI CI` triggers because the workflow now accepts `kaori/**`.

- [ ] **Step 2: Verify every required job succeeds**

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

Search failed and successful job logs for evidence of application errors, including:

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

Do not treat expected scanner informational output as application failure; inspect context.

- [ ] **Step 4: Verify tests are not accidentally skipped**

Compare expected test categories with `scripts/quality_gate.sh`. Any new skip must be intentional and documented; no `xfail`, marker exclusion, or rule suppression may be introduced solely to get green CI.

- [ ] **Step 5: Verify cache behavior**

On a second source-only commit or rerun with unchanged toolchain inputs, confirm logs show local CI toolchain reuse and cached package/security DB downloads while the full validation commands still execute.

- [ ] **Step 6: If a failure exists, stop and debug root cause**

Use systematic debugging: fetch job logs, identify the failing component, reproduce with the same command, implement the smallest root-cause fix, rerun targeted validation, then rerun full CI.

---

### Task 9: Integrate Governance Increment into `kaori/staging` and Perform Local UAT

**Files:**
- No new files unless UAT discovers a defect.

**Interfaces:**
- Consumes: Fully green governance/CI implementation branch.
- Produces: Staging increment ready for explicit local UAT.

- [ ] **Step 1: Integrate the green implementation branch into `kaori/staging`**

Use a non-destructive integration preserving history. Do not merge to `main` yet.

- [ ] **Step 2: Verify staging full CI**

Because `kaori/staging` matches `kaori/**`, a full CI run must execute on the staging integration SHA. All required jobs and `KAORI CI Admission` must pass.

- [ ] **Step 3: User syncs staging locally**

From the user's repository:

```bash
git fetch origin
git switch kaori/staging
git pull --ff-only origin kaori/staging
```

If the local branch does not yet exist:

```bash
git fetch origin
git switch --track -c kaori/staging origin/kaori/staging
```

- [ ] **Step 4: Local Dev Container UAT**

Perform application-level smoke/regression checks relevant to the increment. Confirm development container startup, frontend build/reproducibility, representative application navigation, Reports behavior affected by current fixes, and no local compose/worker regression.

- [ ] **Step 5: Record UAT result on governed Issues**

If accepted, record explicit UAT evidence and move items to `Done`. If rejected, move the affected item back to `In Progress` or `Blocked`, document evidence, and create/continue an issue-linked fix branch.

---

### Task 10: Promote Accepted Staging Increment to `main` and Retire Temporary Branches

**Files:**
- No source changes unless PR review identifies defects.

**Interfaces:**
- Consumes: `kaori/staging` with green full CI and explicit UAT approval.
- Produces: Mainline accepted increment, synchronized staging lineage, and clean branch inventory.

- [ ] **Step 1: Create explicit PR `kaori/staging -> main`**

PR must reference the Governance Epic and included child Issues, include CI evidence, local UAT evidence, migration/security/observability impact, and release impact.

- [ ] **Step 2: Run full PR CI**

Do not merge until the PR integration result passes all required gates.

- [ ] **Step 3: Merge using merge commit only after explicit user approval**

Do not auto-merge. User approval remains the merge authority.

- [ ] **Step 4: Synchronize staging to main**

After merge:

```bash
git fetch origin
git switch kaori/staging
git merge --ff-only origin/main
git push origin kaori/staging
```

If the merge commit topology prevents a direct fast-forward because staging is a parent of the merge commit, `origin/main` should be a descendant and the fast-forward succeeds. If it does not, stop and investigate rather than rewriting history.

- [ ] **Step 5: Retire `kaori/working`**

First verify no unique commits remain:

```bash
git fetch origin
git log --oneline origin/kaori/staging..origin/kaori/working
```

Expected: no output. Then delete the retired branch:

```bash
git push origin --delete kaori/working
git branch -D kaori/working 2>/dev/null || true
```

Do not delete it if unique commits remain; reconcile them through a governed work item first.

- [ ] **Step 6: Delete merged temporary branches**

For each temporary branch whose changes are integrated and no active follow-up depends on it:

```bash
git push origin --delete <temporary-branch>
git branch -D <temporary-branch> 2>/dev/null || true
```

Keep only `main`, `kaori/staging`, and any currently active governed work branches.

- [ ] **Step 7: Close governance implementation Issues only after UAT evidence is recorded**

The Epic may close when all Governance v1 exit criteria are satisfied. If Project metadata still requires a one-time UI action, keep the relevant Task open rather than declaring the Epic complete prematurely.
