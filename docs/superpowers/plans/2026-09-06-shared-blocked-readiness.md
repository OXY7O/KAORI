# Shared Blocked Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify KAORI dashboard readiness, operational workspace blocking, and analytics dependency blocking across Kubernetes and Object Storage without changing the accepted Violet Hero geometry or domain-specific authorization semantics.

**Architecture:** Keep `components/page_hero.html` as Hero authority, `components/states/_blocked_state.html` as section/table blocked-state authority, and `components/dependencies/_blocker.html` as analytics dependency-path authority. Domain templates provide semantic values only; shared primitives own the repeated blocked/readiness structure. Dashboard, operational workspace, and analytics are separate profiles and therefore may use different semantic slots, but same profile + blocked state must render the same grammar across domains.

**Tech Stack:** Flask, Jinja2, HTMX, Tailwind CSS, pytest contract tests, djLint, Ruff/Pyright and existing KAORI verification scripts.

**Spec:** GitHub Issue #206 and `docs/design/components/HERO.md`.

## Global Constraints

- Preserve KAORI Hero Standard v1.6 geometry, Violet identity, dark-mode ownership, accessibility, and HTMX stability.
- Preserve Kubernetes Operations/Governance as the operational-workspace blocked reference.
- Preserve Kubernetes Operations Dashboard as the Operational Dashboard blocked reference.
- Do not duplicate Hero shell/layout/typography geometry in domain templates.
- Do not bypass `clusters.manage` / `integrations.manage` permission boundaries.
- Do not add custom verification scripts; use existing KAORI checks only.
- No schema, migration, retained-data, secret, or provider-query behavior changes.

---

### Task 1: Lock the shared blocked-readiness contracts

**Files:**
- Modify: `tests/contracts/design/test_hero_component_standard_contract.py`
- Modify: `tests/contracts/dashboards/test_operational_dashboard_family_standard_contract.py`
- Create: `tests/contracts/design/test_blocked_readiness_consistency_contract.py`

**Interfaces:**
- Consumes: existing Hero v1.6 macros and blocked-state templates.
- Produces: regression requirements for shared Hero blocked context, dashboard parity, operational-workspace parity, and analytics blocker hierarchy.

- [ ] **Step 1: Write failing contracts**

Require:
- a reusable blocked context body macro in `page_hero.html`;
- Object Storage Dashboard derives blocked state from system availability and provides setup title/info;
- Kubernetes/Object Storage blocked-context wrappers consume the same shared blocked context body;
- Kubernetes/Object Storage analytics blocked-posture wrappers consume the same shared blocked context body and expose `Active Scope` + `Missing Evidence` semantics;
- dependency blocker exposes `Analytics Setup Path`, `Current Blocker`, a missing-dependency summary, and a primary action;
- Object Storage Dashboard uses the shared Object Storage onboarding banner instead of an incomplete local blocker.

- [ ] **Step 2: Run focused contracts and capture expected RED evidence**

Run:

```bash
python -m pytest -q \
  tests/contracts/design/test_hero_component_standard_contract.py \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py \
  tests/contracts/dashboards/test_operational_dashboard_family_standard_contract.py
```

Expected: FAIL only on newly introduced #206 requirements.

- [ ] **Step 3: Commit the RED contracts**

```bash
git add tests/contracts/design/test_hero_component_standard_contract.py \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py \
  tests/contracts/dashboards/test_operational_dashboard_family_standard_contract.py
git commit -m "test(ui): lock shared blocked readiness contract #206"
```

### Task 2: Centralize blocked Hero context composition

**Files:**
- Modify: `app/templates/components/page_hero.html`
- Modify: `app/templates/components/cluster/_hero_blocked_context.html`
- Modify: `app/templates/storage/object_storage/inventory/components/_hero_blocked_context.html`

**Interfaces:**
- Consumes: `context_header`, `context_header_status`, `context_metric`, `context_info`, existing context panel geometry.
- Produces: `blocked_context_body(...)`, a shared renderer for blocked Hero-right panels with profile-selected header accessory and exactly two metrics.

- [ ] **Step 1: Implement the minimum shared blocked context macro**

The macro accepts eyebrow/title, exactly two semantic metrics, one concise information strip, and either status-header or icon-header presentation. It must reuse the existing context panel classes and keep the current geometry unchanged.

- [ ] **Step 2: Migrate Kubernetes operational-workspace blocked context**

Keep the Kubernetes Operations/Governance semantics (`Connected Clusters`, `Workspace State`, setup information) while moving its repeated structure into the shared macro.

- [ ] **Step 3: Migrate Object Storage inventory/workspace blocked context**

Keep Object Storage semantics (`Registered Systems`, `Workspace State`, setup information) while consuming the same shared macro used by the Kubernetes operational-workspace wrapper.

- [ ] **Step 4: Run focused Hero/blocked contracts**

```bash
python -m pytest -q \
  tests/contracts/design/test_hero_component_standard_contract.py \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py
python scripts/verify_hero_component_standard.py
```

### Task 3: Align Object Storage Dashboard blocked state and onboarding

**Files:**
- Modify: `app/templates/storage/object_storage/dashboard/partials/_hero.html`
- Modify: `app/templates/storage/object_storage/dashboard/partials/_content.html`
- Modify: `app/templates/storage/object_storage/inventory/components/_onboarding_banner.html` only if copy/parameterization is required for dashboard reuse.

**Interfaces:**
- Consumes: `page_hero.operational_dashboard(...)` and shared `_blocked_state.html` onboarding grammar.
- Produces: Object Storage Dashboard blocked Hero and onboarding behavior equivalent to Kubernetes Dashboard.

- [ ] **Step 1: Derive dashboard state from `dashboard.systems`**

Use `blocked` when no Object Storage system exists; preserve `normal` for configured dashboards. Blocked title: `Object Storage Setup Required`. Blocked information: `Register an Object Storage system to activate operational signals.`

- [ ] **Step 2: Replace the incomplete local dashboard blocker**

Use the shared Object Storage onboarding banner / shared `_blocked_state.html` configuration with setup status, ordered steps, permission-aware primary action, and domain-correct copy.

- [ ] **Step 3: Run dashboard family contracts**

```bash
python -m pytest -q \
  tests/contracts/dashboards/test_operational_dashboard_family_standard_contract.py \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py
```

### Task 4: Redesign Analytics blocked Hero posture

**Files:**
- Modify: `app/templates/kubernetes/analytics/components/_blocked_posture.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html`

**Interfaces:**
- Consumes: dependency blocker dictionaries and `page_hero.blocked_context_body(...)`.
- Produces: blocked Analytics Hero-right panels that prioritize active scope and missing evidence/dependency.

- [ ] **Step 1: Map Kubernetes blocker kinds to concise missing-evidence semantics**

Use the existing blocker kinds and action authority. Stage 1 maps to cluster context, Stage 2 metrics blockers map to operational metrics, and Stage 3 alert blockers map to alert evidence. The Hero remains summary-only; remediation stays below.

- [ ] **Step 2: Map Object Storage blocker kinds to concise missing-evidence semantics**

Map system/inventory/metrics/snapshot blocker kinds to System Context, Inventory Snapshot, Operational Metrics, or Analytics Snapshot respectively.

- [ ] **Step 3: Render both domains through the shared blocked context body**

Use status-header presentation for Analytics blocked readiness. Metrics are `Active Scope` then `Missing Evidence`.

- [ ] **Step 4: Run Analytics Hero contracts**

```bash
python -m pytest -q \
  tests/contracts/analytics/test_all_analytics_hero_standard_contract.py \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py
```

### Task 5: Clarify the shared Analytics dependency blocker

**Files:**
- Modify: `app/templates/components/dependencies/_blocker.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html`

**Interfaces:**
- Consumes: `dependency_blocker.stage`, title/description/diagnostic, action label and either `action_url` or `action_endpoint`; domain step arrays.
- Produces: one setup-path hierarchy with Complete / Current Blocker / Pending and one permission-aware current-blocker action.

- [ ] **Step 1: Keep the three-step path but strengthen the current-blocker hierarchy**

Retain completed/current/pending state cards, visually emphasize only the current blocker, and keep route context secondary.

- [ ] **Step 2: Add a focused missing-dependency action row**

Show `Missing dependency: <semantic label>`, one concise helper, and the authoritative existing blocker action. Respect K8s `permission` when present; Object Storage continues to use its existing integration endpoints.

- [ ] **Step 3: Run focused dependency contracts**

```bash
python -m pytest -q \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py \
  tests/contracts/analytics
```

### Task 6: Synchronize design documentation and verifier expectations

**Files:**
- Modify: `docs/design/components/HERO.md`
- Modify: `docs/design/patterns/OPERATIONAL_DASHBOARD.md`
- Modify: `docs/design/components/ANALYTICS_HERO.md`
- Modify: `scripts/verify_hero_component_standard.py` only if the new public macro contract requires enforcement.
- Modify: `tests/contracts/design/test_hero_component_standard_contract.py`

**Interfaces:**
- Consumes: implemented shared blocked/readiness behavior.
- Produces: authoritative contract documenting profile-specific blocked grammar and shared ownership.

- [ ] **Step 1: Document profile-specific blocked grammar**

Document that Dashboard blocked uses Dashboard Readiness + Active Scope + Data Authority; operational-workspace blocked follows the Kubernetes Operations/Governance context pattern; Analytics blocked uses Analytics Readiness + Active Scope + Missing Evidence; detailed remediation belongs below the Hero.

- [ ] **Step 2: Update public macro/enforcement contract**

Record the shared blocked context renderer and ensure the verifier/test contract rejects domain-local repeated blocked Hero composition where a shared wrapper exists.

- [ ] **Step 3: Run canonical design verification**

```bash
python scripts/verify_hero_component_standard.py
python -m pytest -q \
  tests/contracts/design/test_hero_component_standard_contract.py \
  tests/contracts/design/test_dark_mode_standard_contract.py \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py \
  tests/contracts/dashboards/test_operational_dashboard_family_standard_contract.py \
  tests/contracts/analytics/test_all_analytics_hero_standard_contract.py
```

### Task 7: Final branch validation and governed staging handoff

**Files:**
- All files changed by Tasks 1–6.

**Interfaces:**
- Consumes: the complete #206 implementation.
- Produces: a frozen work-branch candidate ready for Developer Check and staging review.

- [ ] **Step 1: Run relevant existing formatting/quality checks**

```bash
ruff format --check app tests scripts
ruff check app tests scripts
djlint app/templates --check
python scripts/verify_hero_component_standard.py
python -m pytest -q \
  tests/contracts/design/test_hero_component_standard_contract.py \
  tests/contracts/design/test_dark_mode_standard_contract.py \
  tests/contracts/design/test_blocked_readiness_consistency_contract.py \
  tests/contracts/dashboards/test_operational_dashboard_family_standard_contract.py \
  tests/contracts/analytics/test_all_analytics_hero_standard_contract.py
```

Use the repository Developer Check as branch validation authority; do not add a custom check script.

- [ ] **Step 2: Review branch diff against Issue #206 acceptance criteria**

Confirm no unrelated runtime/data/security changes and no page-local Hero geometry forks.

- [ ] **Step 3: Commit final implementation and open/update the governed PR to `kaori/staging`**

Use `Refs #206` while staging/UAT is pending. Full Admission and Local UAT remain post-merge gates before the Issue can be marked Done or promoted to `main`.
