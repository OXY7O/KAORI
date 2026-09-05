# Canonical Hero Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade KAORI Hero Standard v1.5 to v1.6 with one canonical reusable renderer/profile contract and migrate the authenticated Hero estate without changing the accepted visual baseline.

**Architecture:** Keep `app/templates/components/page_hero.html` as the single visual owner. Add a full renderer that accepts semantic profile/state plus content values, while existing low-level helpers become renderer implementation details. Domain templates may supply values and explicitly exceptional context bodies, but may not assemble Hero shell/layout/content geometry. Verifiers and contracts discover unmanaged Hero shells and protect same-profile parity.

**Tech Stack:** Flask, Jinja, Tailwind, pytest, repository verification scripts.

**Spec:** `docs/design/components/HERO.md`

## Global Constraints

- Preserve the accepted v1.5 geometry, typography, Violet identity surface, dark-mode ownership, accessibility, and HTMX stability.
- Hero profiles and states are semantic contracts, not new page-local visual variants.
- Normal operational Hero metadata is exactly three items.
- Landing is an explicit profile exception; Blocked and Degraded remain explicit states.
- Kubernetes and Object Storage dashboards use the same Operational Dashboard profile grammar.
- No custom one-off migration script is added to the repository.

---

### Task 1: Add RED ownership and parity contracts

**Files:**
- Create: `tests/contracts/design/test_hero_profile_renderer_contract.py`
- Modify later: `scripts/verify_hero_component_standard.py`

- [ ] Add contracts requiring a canonical `page_hero.render(...)` entry point.
- [ ] Require authenticated Hero consumers to stop calling `page_hero.shell_classes()` directly.
- [ ] Add paired Operational Dashboard profile/state and semantic-slot assertions.
- [ ] Run Developer Check and capture expected RED evidence.

### Task 2: Implement the canonical renderer and v1.6 verifier

**Files:**
- Modify: `app/templates/components/page_hero.html`
- Modify: `scripts/verify_hero_component_standard.py`
- Modify: `tests/contracts/design/test_hero_component_standard_contract.py`

- [ ] Add the renderer while preserving all current geometry and shared helper behavior.
- [ ] Add explicit profile/state registry values and semantic metadata rendering.
- [ ] Make the verifier reject direct consumer shell composition and unmanaged Hero identity surfaces.
- [ ] Keep approved context header accessory variants and two-metric maximum.

### Task 3: Migrate Hero consumers and repair semantic drift

**Files:**
- Modify: authenticated templates identified by the RED contract.
- Modify: `app/templates/kubernetes/dashboard/partials/_hero.html`
- Modify: `app/templates/storage/object_storage/dashboard/partials/_hero.html`
- Modify: `app/templates/storage/object_storage/analytics/partials/_hero.html`

- [ ] Migrate page/family Hero shells to `page_hero.render(...)`.
- [ ] Normalize Dashboard context to Active Scope + Data Authority and one readiness/source-management action role.
- [ ] Keep domain-specific nouns/values while preserving identical Dashboard grammar.
- [ ] Make Object Storage Analytics Normal metadata always exactly three using explicit factual inventory evidence state.
- [ ] Preserve Landing/Blocked/Degraded semantics.

### Task 4: Lock documentation and validation

**Files:**
- Modify: `docs/design/components/HERO.md`
- Modify: `docs/design/components/ANALYTICS_HERO.md`
- Modify: `docs/design/patterns/OPERATIONAL_DASHBOARD.md`
- Create: `docs/design/audits/HERO_REUSABILITY_PROFILE_AUDIT_2026_09.md`

- [ ] Bump Hero Standard v1.5 to v1.6.
- [ ] Document Profile vs State, canonical renderer ownership, metadata cardinality, and family parity.
- [ ] Update dashboard/analytics extensions to stop authorizing local shell composition.
- [ ] Record the migration audit and zero-unmanaged-Hero expectation.
- [ ] Run Hero verifier, focused contracts, Developer Check, and staging Full Admission.
- [ ] Open PR to `kaori/staging`, merge after green branch validation, and stop at UAT before `main` promotion.
