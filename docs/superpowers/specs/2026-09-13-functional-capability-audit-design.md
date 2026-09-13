# KAORI Functional Capability Audit Design

**Issue:** #225  
**Status:** Design authority — awaiting user review  
**Base authority:** `kaori/staging@6847255790cb184f3b3beaeeaee80e2173d43f9c`  
**Governing milestone:** UI & Functional Quality (#3)  
**Scope:** Product-wide functional capability accountability, evidence mapping, and defect disposition

## Problem

KAORI already has substantial functional, contract, security, rendering, integration, browser, and E2E coverage, but there is no single fail-closed authority proving that every active product capability is represented by appropriate release evidence.

The existing release surface registry answers **which surfaces ship**. The global UI standard audit matrix answers **which UI standards and delegated workstreams own those surfaces**. The quality gate executes broad functional, domain characterization, contract/migration, and E2E suites. None of those authorities alone answer the #225 question:

> For every active KAORI capability, which user-visible behavior is expected, which evidence proves it, and what is the explicit disposition when evidence or behavior is incomplete?

Without that accountability layer, a capability can be present in navigation and production code while relying on incidental coverage, or a missing functional path can remain invisible until human UAT.

## Goals

1. Represent every active release surface from `scripts/release_surface_registry.py` in one functional capability audit matrix.
2. Decompose each release surface into meaningful user-facing capabilities rather than treating an entire domain as one boolean coverage item.
3. Declare the behavior dimensions that each capability is expected to support, such as normal flow, authorization, validation/dependency handling, persistence, asynchronous jobs, exports, and failure/recovery.
4. Bind each expected behavior to existing executable evidence where it already exists.
5. Fail closed when a release surface, active capability, required behavior, or referenced evidence disappears without an explicit disposition.
6. Turn genuine behavior/evidence gaps into bounded findings or child issues rather than silently expanding a monolithic test suite.
7. Reuse existing KAORI test and verifier authorities; do not create a parallel functional-test framework or a new custom verifier script.
8. Provide #228 Runtime & Error-State Audit with a trustworthy inventory of active capabilities and their dependency/failure expectations.

## Non-Goals

- Rewriting existing functional, contract, integration, rendering, security, browser, or E2E tests.
- Adding a second test runner or a second CI workflow.
- Replacing `scripts/release_surface_registry.py` as the shipping-surface authority.
- Treating a static matrix as proof that runtime behavior works; executable tests remain the behavior authority.
- Fixing product behavior before the audit identifies a concrete defect.
- Expanding Kubernetes Tenant Management (#61, #112–#125).
- Promoting to `main`, creating an RC/tag, or deploying to the staging server as part of the initial #225 inventory increment.

## Existing Authorities Reused

### Release-surface authority

`scripts/release_surface_registry.py` is the canonical list of release-visible and system surfaces. The #225 matrix must cover its surface keys exactly, including the non-UI `health` surface.

The matrix must not invent a second independent list of shipped domains. If the release registry gains or removes a surface, the #225 release contract must fail until the functional matrix is updated in the same governed change.

### UI audit authority

`docs/architecture/ui-standard-audit-matrix.json` already delegates `functional_capability` to #225 for each UI surface. #225 consumes that delegation; it does not duplicate #223 visual/style ownership.

### Full Admission execution authority

`scripts/quality_gate.sh` already provides the required execution layers:

- Contract & Migration Safety (`tests/contracts`, `tests/migrations`).
- Functional Tests (`pytest -m 'not debug and not e2e'`).
- Domain Characterization Tests for reviewed application domains.
- End-to-End Tests (`tests/e2e -m e2e`).
- Static domain/capability verifiers.
- Security, rendering, integration, browser, and other suites included by the global functional selection.

The matrix references those executable assets. It does not execute them itself.

### Existing test-governance authority

`verify_test_domain_architecture.py`, `verify_test_taxonomy.py`, `verify_test_source_paths.py`, and `verify_feature_test_coverage.py` remain in force. #225 may expose missing domain accountability in those authorities, but it does not weaken or bypass them.

## Architecture

The initial implementation adds two product-independent governance artifacts after this design is approved and an implementation plan is written:

1. `docs/architecture/functional-capability-audit-matrix.json`
2. `tests/contracts/release/test_functional_capability_audit_contract.py`

No production application file is part of the first increment.

The matrix is a reviewed inventory plus evidence map. The release contract is the fail-closed guard that checks matrix completeness, evidence-path existence, disposition validity, and alignment with the release registry.

## Matrix Data Model

The matrix uses a deliberately small schema so it remains reviewable.

Top-level fields:

```text
version
phase
source_registry
execution_authorities
behavior_dimensions
surfaces
```

### `version`

Schema version. Initial value: `1`.

### `phase`

Initial phase: `inventory`.

The matrix must not claim milestone completion merely because inventory is complete. Later changes may advance individual capability dispositions, but the initial contract must continue to recognize the matrix as an audit inventory until #225 closure evidence is complete.

### `source_registry`

Must be exactly:

```text
scripts/release_surface_registry.py
```

### `execution_authorities`

Records the existing governed execution layers rather than inventing new ones. At minimum:

- `scripts/quality_gate.sh`
- `scripts/verify_feature_test_coverage.py`
- `scripts/verify_test_domain_architecture.py`
- `tests/contracts`
- `tests/e2e`

The release contract validates referenced paths exist.

### `behavior_dimensions`

The canonical vocabulary for capability expectations:

- `normal_flow` — the primary user-visible success path.
- `authorization` — role/permission denial or allowed-action behavior where access control applies.
- `validation_dependency` — invalid input or required dependency/selection behavior.
- `persistence` — committed state survives the request/transaction boundary where the capability mutates durable data.
- `async_job` — queue/worker lifecycle where the capability delegates work asynchronously.
- `export_publication` — generated/downloadable/publication behavior for report/export capabilities.
- `failure_recovery` — runtime failure, retry, degraded, blocked, or recovery behavior; detailed UX ownership remains #228.

Not every capability requires every dimension. Each capability declares only the dimensions that are semantically expected.

## Surface and Capability Model

`surfaces` must match the release registry surface keys exactly.

Each active UI surface uses this shape:

```text
classification: active_ui
entrypoints: [...]
release_evidence:
  verifiers: [...]
  contract_paths: [...]
capabilities:
  <capability-key>:
    state: active
    behaviors:
      <behavior-dimension>:
        state: covered | bounded_gap | not_applicable
        evidence: [...]              # required only for covered
        reason: ...                  # required for bounded_gap/not_applicable
        tracking_issue: 225          # required for bounded_gap
```

`health` is represented as `system_non_ui` and maps its liveness/readiness behavior to the existing release endpoint/integration authority.

`release_evidence` preserves the owning surface's static verifier and contract authority from `scripts/release_surface_registry.py`. Capability-level behavior evidence is additional accountability and does not replace that release evidence.

### Canonical capability groups

The initial matrix must represent the following product areas, organized under their release surface owners:

- Welcome: authenticated landing/workspace entry behavior.
- Operational Dashboards: Kubernetes and Object Storage dashboard access/read behavior.
- Kubernetes Inventory: overview, nodes, namespaces, workloads, pods, services, ingresses, storage, configuration, topology.
- Object Storage Inventory: overview, systems, buckets, committed snapshot/read behavior.
- Kubernetes Operations: ConfigMap and Secret operational flows, including governed mutation/reveal paths already active in the product.
- Kubernetes Governance: TLS certificate governance/sync/read behavior.
- Analytics: Kubernetes analytics and Object Storage analytics, including overview, utilization/capacity/performance/forecast/top-consumer/alert families that are active.
- Intelligence: Recommendations, Alert Intelligence, Rule Catalog, Automation Control.
- Reports: overview, generation, generated reports, templates, schedules, storage, governed PDF/XLSX/CSV publication where active.
- Integrations: Kubernetes registration/runtime, Prometheus, Alertmanager, Object Storage provider behavior, provider binding/validation/runtime, Notification Channels.
- Platform Operations: overview, jobs/executions, data lifecycle, Kubernetes operational center where active.
- Access: users, roles, permissions, identity providers/provisioning, activity audit.
- Settings: General and Account behavior.
- Authentication: login/logout/session/readiness behavior.
- Notifications: Notification Center, inbox/activity/notification behavior and refresh/read-state flows where active.
- Runtime Health: liveness/readiness endpoints as a non-UI system capability.

Search and shared shell interaction behavior remain coordinated with #226. Accessibility semantics remain #227. The matrix may reference their tests when they prove functional reachability, but #225 does not reopen those workstreams.

## Behavior Evidence States

Every declared behavior has exactly one of three valid states.

### Covered

A `covered` behavior references one or more existing executable evidence paths. Evidence may include:

- contract tests;
- functional/domain characterization tests;
- unit tests when they prove a bounded policy/state transition;
- integration tests for repositories, provider boundaries, persistence, or external-dependency adapters;
- security tests for permission/authentication behavior;
- rendering/browser tests where user-visible reachability is the behavior under audit;
- E2E tests for representative end-to-end release flows;
- existing `verify_*` authorities when the behavior is a static architectural or publication contract.

A path reference is not enough by itself if it is unrelated to the declared behavior. Matrix review keeps each mapping explicit and narrow; the release contract validates structure and path existence, not semantic truth by string matching.

### Bounded gap

If an expected behavior does not yet have adequate evidence, it must not be marked covered. It is recorded as:

```text
state: bounded_gap
reason: <non-empty explanation>
tracking_issue: <positive issue number>
```

During the first inventory increment, `tracking_issue: 225` is allowed for an audit finding that still needs decomposition. Before #225 closes, critical/high product defects must have a dedicated linked issue or be resolved in a bounded child increment. Lower-risk non-defects may remain explicitly dispositioned only when the reason is durable and truthful.

### Not applicable

`not_applicable` is valid only for a behavior dimension that genuinely does not apply to the capability and must include a non-empty reason. It cannot be used as a blanket substitute for missing evidence.

## Fail-Closed Contract Rules

`test_functional_capability_audit_contract.py` must enforce at least the following:

1. The matrix exists, parses, uses schema version `1`, and names the canonical release registry.
2. Matrix surface keys exactly equal `ReleaseSurface.key` values from `scripts/release_surface_registry.py`.
3. UI surfaces are `active_ui`; `health` is explicitly `system_non_ui`.
4. Every active UI surface has at least one capability.
5. Every capability has `state: active` and at least one behavior entry.
6. Every behavior key uses the canonical behavior-dimension vocabulary.
7. Every behavior has exactly one explicit state: `covered`, `bounded_gap`, or `not_applicable`.
8. `covered` entries reference at least one existing evidence path and do not carry a gap disposition.
9. `bounded_gap` entries include a non-empty reason and positive tracking issue number.
10. `not_applicable` entries include a non-empty reason and do not pretend to have executable evidence.
11. No evidence path may point to `tests/debug` or another non-release/debug-only authority.
12. Each surface's `release_evidence.verifiers` and `release_evidence.contract_paths` include all registry-owned verifier/contract paths for that surface.
13. Registry navigation endpoints for a surface are represented by that surface's `entrypoints`; additional non-navigation action/runtime entrypoints may also be listed when required for capability clarity.
14. All referenced execution/evidence paths exist in the repository.
15. The matrix records `phase: inventory` until closure criteria are explicitly met in a later governed change.

The first TDD RED must be caused by the missing matrix/authority itself, not by changing production behavior.

## TDD Strategy

After the spec and implementation plan are approved:

1. Create the release contract first while production and architecture data remain unchanged.
2. Run the path-aware Developer Check and require a valid RED after prerequisite formatting/static/type gates pass.
3. RED should fail because `functional-capability-audit-matrix.json` is absent or incomplete.
4. Add the minimum matrix required to make the contract GREEN using existing evidence.
5. Do not create product fixes merely to make the inventory GREEN. Genuine uncovered behavior is represented as `bounded_gap` with explicit tracking.
6. Run exact-head Developer Check before any PR Ready transition.
7. Subsequent child repairs follow their own RED → GREEN cycle and update the matrix disposition only when evidence exists.

## Audit Execution After Inventory GREEN

The inventory matrix becomes the working checklist for #225.

For each capability:

1. Confirm the declared evidence actually exercises the expected behavior.
2. Confirm permission-sensitive flows have explicit allowed/denied evidence where applicable.
3. Confirm mutation flows have persistence/transaction evidence where applicable.
4. Confirm asynchronous actions have dispatch plus outcome/progress evidence where applicable.
5. Confirm export/publication capabilities have generation and retrieval/publication evidence where applicable.
6. Confirm dependency/validation behavior is deterministic and truthful.
7. Route runtime/degraded UX findings to #228 while keeping functional ownership in #225.

A capability is not considered audited merely because its template or route imports successfully.

## Finding Severity and Disposition

- **Critical/High functional defect:** create or reuse a dedicated linked child issue, repair before milestone completion, add regression evidence, and update the matrix after admission.
- **Medium/Low product defect:** create/link a bounded issue unless the repair is trivially contained within the active #225 increment and does not obscure reviewability.
- **Evidence-only gap:** add focused regression coverage without changing production behavior when the existing behavior is confirmed correct.
- **Intentional/deferred behavior:** document the durable reason and owning issue/roadmap authority; do not represent deferred behavior as active/covered.
- **#228 runtime-state finding:** link the finding to #228 and retain the relevant capability/dependency mapping in #225.

## Relationship to Existing Coverage Governance

`verify_feature_test_coverage.py` currently locks permanent evidence for a reviewed subset of domains. #225 does not immediately expand that verifier simply because the matrix is broader.

The matrix first exposes where permanent multi-layer coverage is absent. If the audit proves `verify_feature_test_coverage.py` itself needs broader permanent domain coverage, that change must be made as a separate bounded TDD increment with a clear RED, rather than hidden inside the inventory commit.

This prevents #225 from conflating two questions:

1. Is every active capability explicitly accounted for?
2. Which permanent test-governance authority should lock the discovered evidence?

## GitHub Delivery Flow

- Parent issue: #225.
- Work branch: `kaori/issue-225-functional-capability-audit` from exact admitted `kaori/staging` authority.
- Draft PR targets `kaori/staging`.
- Design/spec commit precedes implementation planning and code/test changes.
- Implementation begins only after explicit user review of this spec and completion of the implementation plan.
- Draft work uses path-aware Developer Check.
- Ready candidate requires exact-head Developer Check PASS, review/thread lock, and no base drift.
- Merge uses expected-head protection to `kaori/staging`.
- Fresh Full Admission on the exact merged staging SHA is required before a #225 increment is treated as admitted.
- `main`, RC/tag, staging-server deployment, and human UAT remain outside the individual staging-only increment.

## Completion Criteria for #225

#225 may close only when all of the following are true:

1. Every active release surface is represented by the fail-closed functional capability matrix.
2. Every active capability has explicit behavior dimensions.
3. Every declared behavior is backed by relevant executable evidence or an explicit durable disposition.
4. Critical/high functional defects discovered by the audit are resolved and admitted on `kaori/staging`.
5. Remaining lower-risk findings, if any, have explicit linked ownership and do not misrepresent active product behavior.
6. Repaired behavior has focused regression coverage where practical.
7. The final #225 staging SHA receives fresh Full Admission PASS with immutable evidence.
8. The matrix is suitable as the capability inventory consumed by #228 Runtime & Error-State Audit.

Milestone-end human UAT remains a separate program acceptance boundary and is not automatically claimed by closing an individual staging-only audit issue.

## Safety Boundaries

- No custom verifier script is introduced for #225; the fail-closed authority is a release contract using existing test infrastructure.
- No scanner/test waiver, baseline weakening, or broad skip is acceptable as an audit disposition.
- Existing behavior is not rewritten solely to satisfy matrix structure.
- Runtime/degraded presentation remains coordinated with #228.
- Navigation interaction remains coordinated with #226.
- Accessibility remains coordinated with #227.
- Responsive/device behavior remains coordinated with #224.
- `main` is untouched until the governed staging milestone reaches explicit human UAT PASS.
