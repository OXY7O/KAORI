# Kubernetes Analytics Status Notice Border Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the three page-local Kubernetes Analytics status-notice semantic border utilities by delegating border selection to the existing shared `operational_callout.semantic_border_classes` authority without changing the current tone fallback or visual/behavioral contract.

**Architecture:** `_status_notice.html` keeps ownership of its existing background and icon tone selection, but normalizes border tone to the legacy compatibility domain (`critical`, `info`, otherwise `warning`) before calling the shared operational-callout border helper. The focused release contract protects the shared-authority call, zero direct semantic-border literals, exact warning fallback, preserved status-notice structure, and exact style-debt ledger burn-down.

**Tech Stack:** Flask/Jinja, Tailwind CSS static class discovery, pytest release contracts, JSON style-debt governance.

**Spec:** GitHub Issue #285 — UI & Functional Quality — Kubernetes Analytics status notice border authority.

## Global Constraints

- Base from exact admitted `kaori/staging` SHA `3b202824a503702d5d91c2b42b3aacb0ebad144b`.
- `critical` stays critical, `info` stays info, and every other tone continues to fall back to warning for the border.
- Background classes, icon classes, `role="status"`, title/message content, icon rendering, spacing, rounded radius, responsive/mobile layout, `extra_class`, and markup hierarchy remain unchanged.
- Remove only the exact `_status_notice.html` `semantic_border_utilities: 3` style-debt entry.
- Do not modify another residual in this increment.
- `main` remains untouched until explicit UAT PASS.

---

### Task 1: Lock the status-notice border authority contract

**Files:**
- Create: `tests/contracts/release/test_kubernetes_analytics_status_notice_semantic_border_contract.py`

**Interfaces:**
- Consumes: `operational_callout.semantic_border_classes(tone='info', variant='default')` from `app/templates/components/operational_callout.html`.
- Produces: release assertions requiring `_status_notice.html` to call the shared authority while preserving its legacy fallback and structural markers.

- [ ] **Step 1: Write the failing focused release contract**

The contract must assert the shared import/call, exact border-tone normalization, zero direct semantic-border utility literals, preserved background/icon selectors and `role="status"`, and removal of the exact baseline entry.

- [ ] **Step 2: Run Developer Check on the test-only PR head**

Expected: pytest fails exactly because `_status_notice.html` has not yet delegated border selection and because its exact style-debt baseline entry still exists. Formatting/lint/type/migration gates must otherwise remain clean.

- [ ] **Step 3: Record the valid RED head and Developer Check run in PR #286 or the created PR for #285**

Use the actual PR number and run identifiers produced by GitHub; do not reuse example evidence.

### Task 2: Delegate only the status-notice border to shared authority

**Files:**
- Modify: `app/templates/kubernetes/analytics/components/_status_notice.html`
- Modify: `docs/architecture/ui-style-debt-baseline.json`

**Interfaces:**
- Consumes: focused contract from Task 1.
- Produces: one shared-authority border call with legacy warning fallback and zero direct semantic-border literals in `_status_notice.html`.

- [ ] **Step 1: Import shared operational-callout authority**

Add the Jinja import for `components/operational_callout.html` without changing the macro signature or rendered markup hierarchy.

- [ ] **Step 2: Normalize the border tone using the existing compatibility semantics**

Set `border_tone` so only `critical` and `info` pass through and every other value resolves to `warning`.

- [ ] **Step 3: Replace the local border selector only**

Use `operational_callout.semantic_border_classes(border_tone)` for `border_class`. Leave the existing background and icon selectors unchanged.

- [ ] **Step 4: Burn down only the exact ledger entry**

Remove `app/templates/kubernetes/analytics/components/_status_notice.html` and its `semantic_border_utilities: 3` value from `docs/architecture/ui-style-debt-baseline.json`; change no neighboring debt records.

- [ ] **Step 5: Run Developer Check and verify GREEN**

Expected: the focused release contract and the complete Developer Check suite pass from the implementation head.

### Task 3: Admission and merge

**Files:**
- No additional production files.

**Interfaces:**
- Consumes: exact GREEN head from Task 2.
- Produces: expected-head merge into `kaori/staging` and fresh staging admission evidence.

- [ ] **Step 1: Audit PR diff, reviews, review threads, and base drift**

Require zero unexpected files, zero unresolved review threads, zero blocking review state, and base matching the intended staging authority or an explicitly reconciled fast-forward base.

- [ ] **Step 2: Run ready-state Developer Check on the exact final head**

Expected: PASS with no head changes after the run starts.

- [ ] **Step 3: Merge with expected-head protection into `kaori/staging`**

Do not retarget `main`.

- [ ] **Step 4: Verify fresh Full Admission on the exact staging merge SHA**

Require all KAORI CI admission jobs to pass before closing #285.

- [ ] **Step 5: Record evidence and close #285**

Add final admission evidence to the PR, #285, and parent #223. Keep #223 In Progress. Report any GitHub Project fields that require manual user updates.
