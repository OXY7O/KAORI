# Kubernetes Operations Final Recheck — August 2026

## Scope

This final recheck covers the current-release Kubernetes Operations domain:

- ConfigMap Management, Create, Update, and Delete;
- Secret Management, Create, Replace, Delete, and Protected Reveal;
- single and bulk TLS Secret rotation presentation and request ownership;
- shared mutation components, operational feedback, validation gates, and application-shell behavior.

Intelligence and unrelated Platform Operations workflows are outside this review.

## Final product contract

Kubernetes Operations is the explicit live-mutation boundary for ConfigMaps and Secrets. Live Kubernetes owns target identity and execution state. Committed Inventory may provide counters or best-effort consumer evidence but never gates whether a live target may be mutated. Activity Audit and canonical Operational Feedback own actor/outcome evidence.

The mutation request order is:

```text
Authentication
→ RBAC
→ Cluster Prerequisite
→ CSRF / Input Validation
→ Live Kubernetes Validation
→ Mutation
→ Activity Audit / Operational Feedback
```

A clusterless response must never execute before the route permission decorator.

## Mutation Workspace Evolution

The previous 22rem content right rail is retired from ConfigMap CRUD and Secret Create/Replace/Delete/Protected Reveal/Bulk TLS Rotation. Removing the rail alone was not sufficient because the former primary column became visually over-wide. Each workflow was recomposed through shared primitives:

```text
Hero
Evidence Boundary
Target / Identity
Payload / Current State / Impact
Validation Evidence
Workflow Steps + Guardrails
Embedded Action Bar
```

`components/kubernetes_operation_ui.html` owns `workspace_section()` and `workflow_control()`. The latter composes `operational_point_flow`, compact guardrails, warning/help text, and the embedded canonical form action bar. Page-local right-rail or workflow-card variants are not retained.

The Hero right-side context/status/action accessory remains part of the canonical Hero and is not a content rail.

## Workflow dispositions

### ConfigMap Create

- Target & Identity section;
- ConfigMap Entries section with Structured Entry Editor and immutable state;
- persistent validation preview;
- Controlled ConfigMap Creation flow, guardrails, and embedded Validate/Create actions.

### ConfigMap Update

- Live ConfigMap Target;
- Current State & Proposed Change;
- persistent diff/validation preview;
- Controlled ConfigMap Update with embedded Preview/Apply actions.

### ConfigMap Delete

- Live ConfigMap Target;
- best-effort impact + exact-name confirmation;
- non-destructive validation receipt;
- Controlled ConfigMap Deletion plus final destructive confirmation modal.

### Secret Create

- Target & Identity combined in one bounded section;
- responsive Secret Type choice-card group;
- type-specific Secret Content;
- Controlled Secret Creation with No Persistence, Payload-Free Feedback, Metadata Audit, and Create Only guardrails.

### Secret Replace

- Live Secret Target;
- selected-key replacement without rendering current values;
- blank-preserves/current-values-hidden semantics;
- Controlled Secret Replacement with embedded validation/apply actions.

### Secret Delete

- Live Secret Target;
- impact/exact-name confirmation;
- signed receipt + resourceVersion precondition;
- Controlled Secret Deletion plus destructive confirmation modal.

### Protected Reveal

- existing segmented request/requests/approvals workspace retained;
- target, step-up, approval, and one-time protected value remain the primary surface;
- retired right rail replaced by full-width Protected Reveal Lifecycle guidance;
- private-key classes remain rotation-only and are never revealable.

### TLS Rotation

Single TLS rotation retains the compact Governance-aligned full-width evidence workspace. Bulk TLS rotation uses peer upload cards, explicit target selection, and one full-width Controlled Bulk TLS Rotation workflow. Neither uses the retired content rail.

## Security findings

The previous Kubernetes Operations Blueprint `before_request` cluster guard could return onboarding/readiness behavior before route-level permission decorators. It is retired. `cluster_required()` now runs only after `permission_required()` / `any_permission_required()` on every ConfigMap, Secret CRUD, Protected Reveal, and TLS route.

Existing security boundaries remain mandatory:

- CSRF on mutation requests;
- server-side dry-run / fresh validation before apply;
- signed destructive-operation receipts and resourceVersion preconditions;
- no Secret value persistence in KAORI operational records;
- Secret payload scrubbing after provider operations;
- `tls.key` and `ssh-privatekey` blocked from Protected Reveal;
- bounded Kubernetes API timeouts and sanitized provider failures;
- Activity Audit/Notification metadata remains payload-free.

## Legacy and maintainability

The retired Blueprint cluster guard and request-label helper are removed rather than wrapped. `app/kubernetes_operations/secrets/routes.py` and the old domain component wrapper remain absent. Shared `context_rail`, `info_flow`, and information-guide components remain valid for other domains but are no longer imported by the reviewed mutation pages.

## Performance and reliability

Landing counters continue to use committed inventory projections. Live provider calls occur only for explicit operation lookup, validation, or mutation and use bounded request timeouts. HTMX forms retain duplicate-submission protection, validation invalidation, and clean redirect behavior after mutation. The redesign does not introduce additional provider calls.

## Test evidence

Permanent reviewed-domain evidence is organized as:

- L0 Static Quality — final-lock verifier, Ruff/Ruff Format, djLint, Pyright, Prettier, architecture/code-health/source hygiene;
- L1 Contract — `tests/contracts/kubernetes_operations/test_kubernetes_operations_final_release_contract.py` plus existing ConfigMap/Secret contracts;
- L2 Unit — `tests/unit/kubernetes_operations/test_operation_flow.py`;
- L3 Functional — `tests/kubernetes_operations/test_route_authorization_characterization.py` plus existing operation behavior tests;
- L4 Integration — `tests/integration/kubernetes_operations/test_live_runtime_boundary.py`;
- L5 Security Regression — `tests/security/kubernetes_operations/test_kubernetes_operations_security.py`;
- L6 Rendering/UI — `tests/rendering/kubernetes_operations/test_kubernetes_operations_rendering.py`;
- L7 E2E Smoke — `tests/e2e/kubernetes_operations/test_kubernetes_operations_smoke.py`.

## Form + Right Context Browser Correction

Browser review confirmed that both the blanket full-width redesign and the custom v4/v5 task-rail experiments diverged from KAORI's already successful Integration registration forms. Create ConfigMap is therefore rebuilt on the same 12-column composition used by Add Kubernetes Connection and Register Prometheus/Alertmanager Connection, but geometry ownership is now formalized in `components/form_with_context_rail.html`. Experimental task-rail macros are retired. ConfigMap Management and Secret Management keep their existing Hero context box + workflow catalog. The same reviewed geometry is now propagated to Update/Delete ConfigMap, Create/Replace/Delete Secret, and the Protected Reveal `New Request` task. `My Requests` / `Approvals` and TLS workflows retain their dedicated layouts. During the Integrations final recheck, the three original registration pages should migrate to the shared geometry without visual changes.

The functional release gate was also corrected to remove the nonexistent `tests/kubernetes` directory. Kubernetes Operations functional evidence lives under `tests/kubernetes_operations`. Test harnesses were aligned with current RBAC, CSRF, TLS-policy, and SQLAlchemy exception contracts so failures represent production behavior instead of stale fixtures.

## Lock condition

The redesign becomes **PASS — LOCKED** only after authoritative devcontainer Static Quality, Contract, Unit, Functional, Integration, Security, Rendering/UI, E2E smoke, 14-inch/light/dark browser regression, and the canonical `quality_gate.sh --all` pass.
