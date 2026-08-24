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
