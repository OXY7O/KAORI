# KAORI Governance Repository Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Operationalize KAORI Agile SDLC Governance v1 in the repository and GitHub Project through professional Issue Forms, PR evidence, Project metadata, labels, staging branch authority, and lifecycle traceability.

**Architecture:** Repository files define the portable governance contract; the GitHub Project named `KAORI` is the operational board; GitHub Issues are the durable unit of work; `kaori/staging` is the integration/UAT branch; `main` remains the production-ready baseline. Project status and repository labels are deliberately separated so lifecycle state has one authority.

**Tech Stack:** GitHub Issues, GitHub Projects, GitHub Actions, YAML Issue Forms, Markdown, Pytest contract tests, existing KAORI quality gates.

**Spec:** `docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md`

## Global Constraints

- Governance version: `1.0`.
- Long-lived branches: only `main` and `kaori/staging` by default.
- `kaori/working` is retired after migration is verified.
- Temporary branches are deleted after integration when no active dependency remains.
- Default sprint cadence is two weeks and remains flexible.
- `Done` requires explicit local UAT approval from `kaori/staging`.
- GitHub Project `Iteration` is Sprint authority; GitHub Milestone is Release authority.
- Project `Status` is lifecycle authority; do not create `status:*` labels.
- PR creation and merge to `main` remain explicit human gates.
- Current connector cannot create Project custom fields/views or repository label definitions; those one-time metadata steps are applied through GitHub UI using the checked-in authoritative guides.

---

### Task 1: Publish the Canonical Delivery Workflow

**Files:**
- Create: `docs/engineering/KAORI_DELIVERY_WORKFLOW.md`
- Create: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: Governance v1 design.
- Produces: One application-local delivery document referenced by Issue Forms, PR template, Project setup, and future Platform Governance convergence.

- [ ] **Step 1: Write the failing contract test**

Create `tests/contracts/release/test_kaori_delivery_governance_contract.py`:

```python
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md"
WORKFLOW = ROOT / "docs/engineering/KAORI_DELIVERY_WORKFLOW.md"
ISSUE_DIR = ROOT / ".github/ISSUE_TEMPLATE"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_delivery_workflow_locks_branch_and_uat_authority() -> None:
    source = read(WORKFLOW)
    assert "Governance Version: 1.0" in source
    assert "main" in source
    assert "kaori/staging" in source
    assert "kaori/working" in source
    assert "retired" in source.casefold()
    assert "two-week" in source
    assert "Iteration" in source
    assert "Milestone" in source
    assert "Local UAT" in source
    assert "merge commit" in source.casefold()
    assert "Done" in source


def test_design_and_workflow_allow_only_two_default_long_lived_branches() -> None:
    design = read(DESIGN)
    workflow = read(WORKFLOW)
    assert "Only two branches are long-lived by default" in design
    assert "Only two branches are long-lived by default" in workflow
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
```

Expected: FAIL because `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` does not exist.

- [ ] **Step 3: Create the workflow document**

Create `docs/engineering/KAORI_DELIVERY_WORKFLOW.md` with these exact sections and authorities:

```markdown
# KAORI Application Delivery Workflow

**Governance Version: 1.0**
**Scope:** KAORI application repository
**Authority:** Application-local baseline
**Future Authority:** Platform Governance / Platform Workflow standards when formally adopted

## Lifecycle
`Idea / Request -> Epic -> User Story / Bug / Spike -> Refinement -> Ready -> implementation branch -> full CI -> kaori/staging -> full staging CI -> Local UAT -> Accepted -> PR to main -> merge commit -> main`

## Branch Authority
Only two branches are long-lived by default:
- `main` — production-ready baseline and release authority.
- `kaori/staging` — integration and Local UAT authority.

`kaori/working` is retired after migration is verified. Temporary branches are deleted when their work is integrated and no active dependency remains.

## Work Branches
- `kaori/story-<issue>-<slug>`
- `kaori/bug-<issue>-<slug>`
- `kaori/task-<issue>-<slug>`
- `kaori/spike-<issue>-<slug>`
- `kaori/chore-<issue>-<slug>`
- `kaori/hotfix-<issue>-<slug>`

## Sprint and Release
The default Sprint cadence is two-week and flexible. GitHub Project **Iteration** is Sprint authority. GitHub **Milestone** is Release authority. Sprint completion does not force release.

## Definition of Ready
Scope and acceptance criteria are testable; dependencies and design blockers are known; security/data/migration impact is considered; expected verification is known; Story Points are assigned when sprint planning requires them.

## Definition of Done
Code complete and green CI are necessary but not sufficient. Work remains in `UAT` until Local UAT from `kaori/staging` is explicitly approved. Applicable tests, migration checks, documentation, security, runtime, and operational evidence must be healthy.

## Failure Return Paths
Failed CI returns work to `In Progress` or `Blocked`. Failed UAT returns work to `In Progress` or `Blocked` with evidence. No failing change is promoted to `main`.

## Hotfix
`main -> kaori/hotfix-<issue>-<slug> -> full CI -> UAT -> PR main`. After merge, synchronize `kaori/staging` from `main` before normal delivery continues.

## Branch Hygiene
Merged temporary branches are deleted when no active dependency remains. Issues, PRs, commits, releases, and governance records are the durable audit trail.

## Platform Governance Convergence
When Platform Governance / Platform Workflow standards are approved: gap analysis -> terminology/policy mapping -> migration plan -> replace duplicated rules -> reference platform authority -> retain KAORI-specific extensions.
```

- [ ] **Step 4: Run the targeted and static gates**

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
bash scripts/quality_gate.sh --static
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/engineering/KAORI_DELIVERY_WORKFLOW.md tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "docs(governance): publish KAORI delivery workflow v1"
```

---

### Task 2: Add Governed Issue Forms

**Files:**
- Create: `.github/ISSUE_TEMPLATE/epic.yml`
- Create: `.github/ISSUE_TEMPLATE/user-story.yml`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/task.yml`
- Create: `.github/ISSUE_TEMPLATE/spike.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Modify: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: Work-item contracts in Governance v1.
- Produces: Structured GitHub Issue intake for all primary governed work types.

- [ ] **Step 1: Extend the contract test and confirm RED**

Append:

```python

def load_form(name: str) -> dict:
    return yaml.safe_load((ISSUE_DIR / name).read_text(encoding="utf-8"))


def test_issue_forms_cover_primary_governed_types() -> None:
    expected = {
        "epic.yml": ("Epic", "[EPIC] "),
        "user-story.yml": ("User Story", "[STORY] "),
        "bug.yml": ("Bug", "[BUG] "),
        "task.yml": ("Task", "[TASK] "),
        "spike.yml": ("Spike", "[SPIKE] "),
    }
    for filename, (name, prefix) in expected.items():
        form = load_form(filename)
        assert form["name"] == name
        assert form["title"] == prefix
        assert form["body"]


def test_blank_issue_creation_is_disabled() -> None:
    config = load_form("config.yml")
    assert config["blank_issues_enabled"] is False
```

Run the targeted test. Expected: FAIL because Issue Forms do not exist.

- [ ] **Step 2: Create `epic.yml`**

```yaml
name: Epic
description: Define a multi-story KAORI product or platform outcome.
title: "[EPIC] "
body:
  - type: markdown
    attributes:
      value: "Use this form for an outcome that requires multiple governed child work items."
  - type: textarea
    id: outcome
    attributes:
      label: Outcome
      description: Describe the measurable outcome this Epic must produce.
    validations:
      required: true
  - type: textarea
    id: problem
    attributes:
      label: Problem Statement
    validations:
      required: true
  - type: textarea
    id: value
    attributes:
      label: Business / Operational Value
    validations:
      required: true
  - type: textarea
    id: scope
    attributes:
      label: Scope
    validations:
      required: true
  - type: textarea
    id: out_of_scope
    attributes:
      label: Out of Scope
    validations:
      required: true
  - type: textarea
    id: success
    attributes:
      label: Success Metrics
    validations:
      required: true
  - type: textarea
    id: risks
    attributes:
      label: Risks
  - type: textarea
    id: dependencies
    attributes:
      label: Dependencies
  - type: textarea
    id: exit
    attributes:
      label: Exit Criteria
    validations:
      required: true
```

- [ ] **Step 3: Create `user-story.yml`**

```yaml
name: User Story
description: Define a testable user or operator capability.
title: "[STORY] "
body:
  - type: input
    id: persona
    attributes:
      label: Persona
      placeholder: "Platform Operator"
    validations:
      required: true
  - type: textarea
    id: capability
    attributes:
      label: Capability
      description: "As a <persona>, I want <capability>, so that <outcome>."
    validations:
      required: true
  - type: textarea
    id: outcome
    attributes:
      label: Business / Operational Outcome
    validations:
      required: true
  - type: textarea
    id: acceptance
    attributes:
      label: Acceptance Criteria
      description: Use Given / When / Then where practical.
    validations:
      required: true
  - type: textarea
    id: ready
    attributes:
      label: Definition of Ready Evidence
    validations:
      required: true
  - type: textarea
    id: technical
    attributes:
      label: Technical Notes
  - type: textarea
    id: security
    attributes:
      label: Security Considerations
  - type: textarea
    id: migration
    attributes:
      label: Data / Migration Considerations
  - type: textarea
    id: observability
    attributes:
      label: Observability / Operational Considerations
  - type: textarea
    id: tests
    attributes:
      label: Test Strategy
    validations:
      required: true
  - type: textarea
    id: dependencies
    attributes:
      label: Dependencies
  - type: textarea
    id: uat
    attributes:
      label: UAT Evidence
      description: Leave as pending until the change is integrated into kaori/staging.
```

- [ ] **Step 4: Create `bug.yml`**

```yaml
name: Bug
description: Report a reproducible KAORI defect or regression.
title: "[BUG] "
body:
  - type: textarea
    id: observed
    attributes:
      label: Observed Behavior
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Reproduction
    validations:
      required: true
  - type: textarea
    id: impact
    attributes:
      label: Impact
    validations:
      required: true
  - type: textarea
    id: root_cause
    attributes:
      label: Root Cause Evidence
      description: Permanent fixes require root-cause evidence; emergency containment must be identified explicitly.
  - type: textarea
    id: regression
    attributes:
      label: Regression Test
    validations:
      required: true
  - type: textarea
    id: risk
    attributes:
      label: Security / Data / Migration Impact
  - type: textarea
    id: uat
    attributes:
      label: UAT Evidence
```

- [ ] **Step 5: Create `task.yml`, `spike.yml`, and `config.yml`**

`task.yml`:

```yaml
name: Task
description: Track a concrete implementation or operational deliverable.
title: "[TASK] "
body:
  - type: input
    id: parent
    attributes:
      label: Parent Work Item
      description: Reference the parent Epic, Story, Bug, or governance activity.
    validations:
      required: true
  - type: textarea
    id: deliverable
    attributes:
      label: Deliverable
    validations:
      required: true
  - type: textarea
    id: completion
    attributes:
      label: Completion Criteria
    validations:
      required: true
  - type: textarea
    id: dependencies
    attributes:
      label: Dependencies
  - type: textarea
    id: verification
    attributes:
      label: Verification
    validations:
      required: true
```

`spike.yml`:

```yaml
name: Spike
description: Timebox research that must end in evidence and a decision.
title: "[SPIKE] "
body:
  - type: textarea
    id: question
    attributes:
      label: Question
    validations:
      required: true
  - type: textarea
    id: hypothesis
    attributes:
      label: Hypothesis
    validations:
      required: true
  - type: input
    id: timebox
    attributes:
      label: Timebox
      placeholder: "4 hours"
    validations:
      required: true
  - type: textarea
    id: evidence
    attributes:
      label: Evidence
  - type: textarea
    id: decision
    attributes:
      label: Decision
  - type: textarea
    id: follow_up
    attributes:
      label: Follow-up Stories / Tasks
```

`config.yml`:

```yaml
blank_issues_enabled: false
contact_links: []
```

- [ ] **Step 6: Verify and commit**

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
bash scripts/quality_gate.sh --static
git add .github/ISSUE_TEMPLATE tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "feat(governance): add governed KAORI issue forms"
```

Expected: PASS.

---

### Task 3: Add the Pull Request Evidence Contract

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: Definition of Done, UAT authority, merge strategy.
- Produces: Consistent PR evidence for work integration and staging-to-main promotion.

- [ ] **Step 1: Extend test and confirm RED**

Append:

```python

def test_pull_request_template_requires_delivery_evidence() -> None:
    source = read(ROOT / ".github/PULL_REQUEST_TEMPLATE.md")
    for token in (
        "Linked Issue",
        "Acceptance Criteria Coverage",
        "Test Evidence",
        "Security Impact",
        "Migration / Data Impact",
        "Observability / Operational Impact",
        "UAT",
        "Release Impact",
        "unexpected skipped tests",
    ):
        assert token in source
```

Run targeted test. Expected: FAIL.

- [ ] **Step 2: Create the PR template**

```markdown
## Linked Issue

Relates to #

## Scope Summary

## Acceptance Criteria Coverage

## Test Evidence

Record targeted tests and the relevant full KAORI CI run.

## Security Impact

## Migration / Data Impact

## Observability / Operational Impact

## UAT

- [ ] Work-branch integration only; local UAT is not yet applicable.
- [ ] `kaori/staging` local UAT passed and evidence is linked below.

UAT evidence:

## Release Impact

## Reviewer Checklist

- [ ] Change matches the linked work item.
- [ ] Required CI is green without suppressed failures.
- [ ] No unexpected skipped tests, tracebacks, HTTP 5xx, migration failures, or runtime failures remain.
- [ ] Frontend/generated artifacts are reproducible when applicable.
- [ ] Security, migration, documentation, and observability impacts are addressed.
- [ ] Staging-to-main promotion has explicit local UAT approval.
```

- [ ] **Step 3: Verify and commit**

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
bash scripts/quality_gate.sh --static
git add .github/PULL_REQUEST_TEMPLATE.md tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "feat(governance): add KAORI pull request evidence contract"
```

Expected: PASS.

---

### Task 4: Define Project Fields, Views, and Label Taxonomy

**Files:**
- Create: `docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md`
- Create: `docs/engineering/KAORI_GITHUB_LABELS.md`
- Modify: `tests/contracts/release/test_kaori_delivery_governance_contract.py`

**Interfaces:**
- Consumes: Project `KAORI` already created by the user.
- Produces: Exact Project and label metadata that can later be migrated to central Platform Governance automation.

- [ ] **Step 1: Add documentation contracts and confirm RED**

Append:

```python

def test_project_setup_defines_canonical_fields_and_views() -> None:
    source = read(ROOT / "docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md")
    for token in (
        "Backlog", "Refinement", "Ready", "In Progress", "Code Review / CI",
        "Staging", "UAT", "Blocked", "Done", "P0 — Critical", "P3 — Low",
        "1, 2, 3, 5, 8, 13", "Product Backlog", "Current Sprint",
        "Active Delivery", "Staging & UAT", "Epics / Roadmap",
        "Bugs & Incidents", "Release Readiness",
    ):
        assert token in source


def test_label_catalog_is_portable_and_has_no_status_labels() -> None:
    source = read(ROOT / "docs/engineering/KAORI_GITHUB_LABELS.md")
    for token in (
        "type:epic", "type:story", "type:bug", "type:task", "type:spike",
        "priority:p0-critical", "priority:p3-low", "area:ci-cd", "area:security",
        "impact:migration", "workflow:blocked", "workflow:expedite",
    ):
        assert token in source
    assert "status:in-progress" not in source
    assert "status:done" not in source
```

Run targeted test. Expected: FAIL.

- [ ] **Step 2: Create the Project setup guide**

`docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md` must define exactly:

```text
Project: KAORI

Status (single select)
Backlog
Refinement
Ready
In Progress
Code Review / CI
Staging
UAT
Blocked
Done

Type (single select)
Epic
User Story
Bug
Task
Spike
Chore
Technical Debt

Priority (single select)
P0 — Critical
P1 — High
P2 — Medium
P3 — Low

Story Points (number)
Planning scale: 1, 2, 3, 5, 8, 13

Iteration
Name: Sprint
Duration: 2 weeks
Carry-over: allowed

Views
Product Backlog: Status Backlog/Refinement/Ready, group by Priority
Current Sprint: current Iteration, group by Status
Active Delivery: In Progress/Code Review / CI/Blocked
Staging & UAT: Staging/UAT/Blocked
Epics / Roadmap: Type Epic
Bugs & Incidents: Type Bug, group by Priority
Release Readiness: release Milestone assigned and not yet released
```

Document one critical automation constraint: do not automatically map every closed Issue to `Done`; Governance v1 requires UAT evidence.

- [ ] **Step 3: Create the label catalog**

`docs/engineering/KAORI_GITHUB_LABELS.md` must define this exact baseline:

```text
type:epic               5319E7  Multi-story product/platform outcome
type:story              7C3AED  User or operator capability
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
area:backend            2563EB  Backend/application services
area:reports            0891B2  Reports/publication
area:intelligence       9333EA  Intelligence domain
area:kubernetes         326CE5  Kubernetes domain
area:object-storage     0F766E  Object Storage domain
area:analytics          4F46E5  Analytics domain
area:integrations       0284C7  Integration providers
area:settings           475569  Settings/identity/access
area:platform           334155  Application platform/foundation
area:ci-cd              0369A1  CI/CD and delivery automation
area:security           BE123C  Security implementation
area:observability      0E7490  Monitoring/observability

impact:breaking         991B1B  Breaking contract/change
impact:migration        C2410C  Schema/data/migration impact
impact:security         BE123C  Security impact
impact:performance      0F766E  Performance impact
impact:accessibility    6D28D9  Accessibility impact

workflow:blocked        111827  Work cannot progress
workflow:expedite       E11D48  Approved expedite/hotfix lane
```

- [ ] **Step 4: Verify and commit**

```bash
pytest -q tests/contracts/release/test_kaori_delivery_governance_contract.py
bash scripts/quality_gate.sh --static
git add docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md docs/engineering/KAORI_GITHUB_LABELS.md tests/contracts/release/test_kaori_delivery_governance_contract.py
git commit -m "docs(governance): define KAORI project and label metadata"
```

Expected: PASS.

- [ ] **Step 5: Apply Project fields/views and labels in GitHub UI**

Use the checked-in guides as the sole authority. The current connector does not expose Project custom-field/view writes or repository label-definition creation, so this is the one manual metadata step. After it is done, Issues and PRs can be managed through the connector using those definitions.

---

### Task 5: Move CI Branch Authority from `kaori/working` to Governed KAORI Branches

**Files:**
- Modify: `.github/workflows/quality.yml`
- Create: `tests/contracts/release/test_github_actions_governance_contract.py`

**Interfaces:**
- Consumes: `kaori/staging` branch authority and temporary `kaori/**` work branches.
- Produces: Full CI on every governed KAORI branch without `paths-ignore` bypasses.

- [ ] **Step 1: Write the failing workflow contract**

Create `tests/contracts/release/test_github_actions_governance_contract.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY = ROOT / ".github/workflows/quality.yml"


def test_quality_workflow_covers_governed_kaori_branches() -> None:
    source = QUALITY.read_text(encoding="utf-8")
    assert '"kaori/**"' in source or "'kaori/**'" in source
    assert "kaori/staging" in source or '"kaori/**"' in source
    assert "kaori/working" not in source
    assert "main" in source
    assert "paths-ignore" not in source
```

Run:

```bash
pytest -q tests/contracts/release/test_github_actions_governance_contract.py
```

Expected: FAIL while the workflow still references `kaori/working`.

- [ ] **Step 2: Change the push branch selector**

Set:

```yaml
push:
  branches:
    - "kaori/**"
    - main
    - "release/**"
```

Keep the existing PR-to-main trigger and fork guard. Do not weaken any job, permission, or admission dependency.

- [ ] **Step 3: Verify and commit**

```bash
pytest -q tests/contracts/release/test_github_actions_governance_contract.py
bash scripts/quality_gate.sh --static
git add .github/workflows/quality.yml tests/contracts/release/test_github_actions_governance_contract.py
git commit -m "ci(governance): adopt staging and governed branch model"
```

Expected: PASS.

---

### Task 6: Bootstrap the Governance Backlog in GitHub Issues

**Files:**
- No application-code files.
- GitHub Issues are the durable records.

**Interfaces:**
- Consumes: Issue Forms, Project metadata, label taxonomy.
- Produces: First professional Epic and child work items.

- [ ] **Step 1: Create the Governance Epic**

Create:

```text
Title: [EPIC] Establish KAORI Agile SDLC Governance v1
Type: Epic
Priority: P1 — High
Areas: area:platform, area:ci-cd
Status: In Progress

Outcome:
KAORI has a versioned application-local Agile/SDLC baseline that can later converge with Platform Governance / Platform Workflow standards.

Exit Criteria:
- Issue Forms and PR template are active.
- Project fields/views match Governance v1.
- label taxonomy is active.
- kaori/staging is the UAT authority.
- full CI runs on governed kaori/** branches.
- staging full CI passes.
- local UAT is explicitly accepted before Done.
- kaori/working is retired when migration is verified.
```

- [ ] **Step 2: Create child work items**

Create these exact items:

```text
[STORY] Standardize KAORI issue and pull-request intake
[TASK] Configure KAORI GitHub Project fields and views
[CHORE] Optimize self-hosted CI caching without reducing validation
[TASK] Retire kaori/working after staging migration
```

Use native sub-issues when available. If native hierarchy is not available in the connector, include `Parent Epic: #<epic-number>` in each body and link them in the Project UI.

- [ ] **Step 3: Apply metadata**

Use Type, Priority, Area, Iteration, Story Points, and Status according to Governance v1. No item may move to `Done` before explicit staging UAT evidence.

---

### Task 7: Integrate Governance v1 into `kaori/staging`, UAT, Promote, and Clean Branches

**Files:**
- No source files unless CI/UAT finds a defect.

**Interfaces:**
- Consumes: Green governance implementation branch.
- Produces: Accepted Governance v1 on staging, then main, with retired temporary branches.

- [ ] **Step 1: Run full CI on the governance implementation branch**

Required jobs must all succeed:

```text
Static, Architecture, and Governance
Secrets, SAST, Dependencies, and Workflow Security
Functional and Integration Tests
Frontend Reproducibility
Production Image, Container Security, Runtime, and DAST
KAORI CI Admission
```

Inspect logs for unexpected tracebacks, assertion failures, HTTP 5xx, migration failures, runtime errors, or unexpected skipped tests even when job conclusions are green.

- [ ] **Step 2: Integrate the green branch into `kaori/staging`**

Preserve history. Do not promote to `main` yet.

- [ ] **Step 3: Require full staging CI**

The staging integration SHA must pass all required jobs and `KAORI CI Admission`.

- [ ] **Step 4: Perform local UAT from staging**

User commands:

```bash
git fetch origin
git switch kaori/staging || git switch --track -c kaori/staging origin/kaori/staging
git pull --ff-only origin kaori/staging
```

Validate Dev Container startup, representative application navigation, affected Reports flows, frontend reproducibility, and compose/worker lifecycle. Record acceptance or rejection on the governed Issues.

- [ ] **Step 5: Create `kaori/staging -> main` PR only after explicit UAT approval**

Include linked Issues, full CI evidence, UAT evidence, migration/security/observability impact, and release impact. Run full PR CI. Do not merge until the user explicitly approves merge.

- [ ] **Step 6: Merge with merge commit and synchronize staging**

After approved merge:

```bash
git fetch origin
git switch kaori/staging
git merge --ff-only origin/main
git push origin kaori/staging
```

Expected: fast-forward because `main` is a descendant of the accepted staging increment. If not, stop and investigate history; do not rewrite it.

- [ ] **Step 7: Retire `kaori/working` safely**

First prove there are no unique commits:

```bash
git fetch origin
git log --oneline origin/kaori/staging..origin/kaori/working
```

Expected: no output. Then:

```bash
git push origin --delete kaori/working
git branch -D kaori/working 2>/dev/null || true
```

If the log is non-empty, create a governed migration Task and reconcile those commits before deletion.

- [ ] **Step 8: Delete merged temporary remote branches**

List merged `kaori/*` branches and delete only branches already contained in `origin/kaori/staging` or `origin/main`:

```bash
git fetch --prune origin
for branch in $(git branch -r --merged origin/kaori/staging | sed 's#^[[:space:]]*origin/##' | grep '^kaori/' | grep -v '^kaori/staging$' | grep -v '^kaori/working$'); do
  git push origin --delete "$branch"
done
```

Then delete `kaori/working` separately after Step 7 proof. Keep active unmerged work branches.
