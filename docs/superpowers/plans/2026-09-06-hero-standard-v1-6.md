# KAORI Hero Standard v1.6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade KAORI Hero ownership from shared visual primitives to canonical reusable profile renderers, align same-context dashboard heroes, and enforce semantic Hero contracts centrally.

**Architecture:** Keep `app/templates/components/page_hero.html` as the single visual source of truth. Add high-level profile renderers that consume semantic values while retaining low-level macros as internal compatibility primitives during migration. Lock Profile + State semantics in verification and contracts, starting with the paired Operational Dashboard family and Object Storage Analytics drift identified in issue #198.

**Tech Stack:** Flask, Jinja, Tailwind CSS, pytest contract tests, KAORI Python verification scripts.

**Spec:** `docs/design/components/HERO.md`

## Global Constraints

- Preserve current Hero geometry, typography, Violet identity surface, dark mode, accessibility, and HTMX stability.
- Active version moves from Hero Standard v1.5 to v1.6.
- State vocabulary remains Landing, Normal, Blocked, and Degraded.
- Same Profile + same State must use one structural Hero grammar.
- Normal operational Hero metadata cardinality is exactly three.
- Context metrics remain limited to two.
- Kubernetes and Object Storage operational dashboards are paired references and must share one dashboard Hero profile.
- Do not fabricate missing operational evidence to fill metadata.

---

### Task 1: Lock the reusable profile contract

**Files:**
- Modify: `tests/contracts/design/test_hero_component_standard_contract.py`
- Modify: `scripts/verify_hero_component_standard.py`

**Interfaces:**
- Consumes: current `page_hero` primitive macro contract.
- Produces: required high-level `operational_dashboard(...)` profile renderer and v1.6 ownership assertions.

- [ ] Add failing contract assertions for v1.6, the canonical dashboard profile renderer, and paired dashboard consumers.
- [ ] Run the focused Hero contract and confirm failure is caused by the missing v1.6 renderer/profile contract.
- [ ] Implement the minimum renderer and verifier ownership checks.
- [ ] Re-run the focused Hero contract until green.

### Task 2: Align paired Operational Dashboard Heroes

**Files:**
- Modify: `app/templates/components/page_hero.html`
- Modify: `app/templates/kubernetes/dashboard/partials/_hero.html`
- Modify: `app/templates/storage/object_storage/dashboard/partials/_hero.html`
- Modify: `docs/design/patterns/OPERATIONAL_DASHBOARD.md`

**Interfaces:**
- Consumes: `page_hero.operational_dashboard(...)`.
- Produces: one Hero grammar with domain-provided title, description, exactly three metadata values, active scope, data authority, and readiness-management action.

- [ ] Write paired-family assertions before changing the templates.
- [ ] Confirm Kubernetes/Object Storage fail the new parity contract.
- [ ] Migrate both dashboard partials to the shared profile renderer.
- [ ] Re-run Hero and operational-dashboard contracts.

### Task 3: Repair Object Storage Analytics Normal metadata

**Files:**
- Modify: `app/templates/storage/object_storage/analytics/partials/_hero.html`
- Modify: `docs/design/components/ANALYTICS_HERO.md`
- Test: existing Object Storage Analytics contracts plus Hero contracts.

**Interfaces:**
- Consumes: Normal operational metadata cardinality rule.
- Produces: exactly three factual metadata items in every Normal branch without inventing missing inventory observations.

- [ ] Add a contract that proves Normal Object Storage Analytics never conditionally drops the third metadata slot.
- [ ] Confirm it fails against the current conditional `Observed` metadata.
- [ ] Replace the conditional third slot with an always-available operational semantic value appropriate to the active analytics route.
- [ ] Re-run focused analytics/Hero contracts.

### Task 4: Synchronize Hero Standard v1.6 documentation and verifier

**Files:**
- Modify: `docs/design/components/HERO.md`
- Modify: `scripts/verify_hero_component_standard.py`
- Modify: `tests/contracts/design/test_hero_component_standard_contract.py`
- Create: `docs/design/audits/HERO_REUSABLE_PROFILE_ALIGNMENT_AUDIT_2026_09.md`

**Interfaces:**
- Consumes: implemented profile renderer and state rules.
- Produces: active v1.6 design contract and audit evidence.

- [ ] Document Profile vs State, dashboard profile semantics, metadata cardinality, and migration ownership.
- [ ] Update verifier tokens and family parity checks.
- [ ] Record the implementation audit and remaining compatibility boundary, if any.
- [ ] Run Hero verifier and focused contract suite.

### Task 5: Admission and UAT handoff

**Files:**
- No production changes unless verification exposes a defect.

**Interfaces:**
- Consumes: completed branch implementation.
- Produces: PR to `kaori/staging` linked to issue #198.

- [ ] Run available Developer Check/CI evidence for the work branch.
- [ ] Review branch diff for unrelated changes.
- [ ] Open PR to `kaori/staging` with issue linkage and UAT scope.
- [ ] Report GitHub Project custom metadata fields that require manual update.
