# Architecture Cycle Remediation — 2026-08-24

## Scope

The final release gate exposed one expanded strongly connected component spanning Alert Intelligence, Analytics, Kubernetes Cluster/Inventory, Integrations, Metrics/Alert sources, and the resolver domain. The fix contracts the graph back to the two existing debt envelopes; it does **not** widen `architecture-debt-baseline.json`.

## Boundary corrections

1. **Cluster deletion → AlertCase source state**
   - Kubernetes Cluster no longer imports Alert Intelligence.
   - Source-deletion state transition is owned by `app/common/alert_case_source_state.py` and reused by Alert Intelligence.

2. **Provider resolver adapter → resolver contracts**
   - Kubernetes provider adapters keep living under Integrations.
   - Cross-domain resolver DTO/protocol and registry primitives are now shared-kernel contracts under `app/common`.
   - `app/intelligence/resolver/contracts.py` and `registry.py` remain compatibility surfaces that re-export the same class identities.

3. **Recommendation alert commands**
   - `app.intelligence.recommendation_alert_commands` is declared as logical Alert Intelligence ownership because it is the AlertCase command boundary consumed by Alert Intelligence routes.
   - Physical relocation can be handled separately; the architecture verifier now reflects current bounded-context ownership without expanding the debt envelope.

## Result

`verify_architecture_boundaries.py` returns only the two pre-existing cycle envelopes:

- `auth, common, extensions, models, notifications, rbac`
- `alert_sources, cluster, integrations, inventory, metrics_sources`

Alert Intelligence, Analytics, Intelligence, and Resolver are no longer members of a top-level dependency cycle.

## 2026-10-15 — Staging admission follow-up

### Import-cycle admission and operation ownership

Full Admission on the reviewed staging candidate exposed a separate **module-level**
runtime-import cycle after the larger cross-domain cycles were contracted.
The canonical `scripts/verify_import_cycles.py` gate and the approved
`docs/architecture/architecture-debt-baseline.json` stay unchanged.

- **Intelligence read model:** both `app/intelligence/overview.py` and
  `app/intelligence/service.py` consume `committed_inventory_coverage.py`.
  Its 24-hour evidence qualification reads committed KAORI SQL state. Neither
  presentation nor recommendation service imports its peer to get coverage.
- **Tenant release orchestration:** `release_handoff_approval.py` and
  `release_preflight.py` call the existing Tenant-owned evidence and
  provider-guard operations through
  `app/kubernetes/tenant/handoff_runtime_operations.py`. The Flask application
  composition root (`app/bootstrap/blueprints.py`) wires the exact canonical
  callables per app; a missing or invalid registration fails closed.
  The business services, signatures, independent approval, immutable plan
  fingerprints, provider identity, native no-transfer recovery, readback and
  AuditEvent authority are **not** transferred into the composition helper.
- **Scope of trust:** a green module import graph proves static dependency
  direction only. Release and infrastructure-mutation correctness still
  require functional, security, runtime, DAST and UAT evidence on the exact
  admitted SHA. Import-cycle admission never substitutes for human UAT.

This records application composition already used for the Tenant Work Inbox
and Capsule RBAC operations, rather than introducing a new provider facade or
widening any historical architecture debt.
