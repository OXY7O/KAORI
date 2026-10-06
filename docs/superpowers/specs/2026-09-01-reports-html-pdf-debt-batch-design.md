# Reports HTML/PDF Debt Batch Design

**Date:** 2026-09-01  
**Parent:** #35  
**Children:** #39, #40, #41, #42, #43, #44  
**Delivery branch:** `feat-68-path-aware-developer-check`  
**Staging PR:** #75

## Decision

The operator explicitly reprioritized the remaining Reports HTML/PDF debt children into one governed delivery batch to amortize the cost of the authoritative Full Admission cycle. This replaces the default one-child-at-a-time sequencing for this delivery only; each child retains its own debt boundary, behavioral guardrails, characterization evidence, scanner evidence, and acceptance state.

The batch does not weaken the parent #35 ceilings or evidence rules. Default ceilings remain exactly `800 / 160 / 30 / 8`, broad exceptions may not increase, and stale debt entries may be removed only after fresh scanner evidence proves the corresponding source debt is resolved.

## Architecture Pattern

Use the completed Capacity Analysis (#36) and Storage Analysis (#38) refactors as the reference pattern:

- keep each public `html_pdf/<family>.py` entrypoint stable;
- move cohesive presentation responsibilities into a family-owned package;
- keep extracted modules/functions below normal code-health ceilings;
- avoid replacement catch-all modules;
- extract shared helpers only when at least two families demonstrate genuinely identical semantics;
- preserve template-facing dictionaries, ordering, recommendation meaning, charts/tables, page breaks, and renderer behavior.

## Per-family ownership targets

### #39 Resource Utilization
Split presentation orchestration and recommendation construction while preserving typography/readability and resource evidence semantics.

### #40 Alerts & Anomalies
Split summary/evidence/response/recommendation assembly while preserving severity and operator-response semantics.

### #41 Forecast Analysis
Split forecast evidence, recommendation plan, and presentation orchestration while preserving historical/projected semantics.

### #42 Analytics Overview
Split cross-domain inventory/readout/evidence/recommendation orchestration while preserving the accepted Analytics Overview PDF baseline.

### #43 Top Consumers
Split ranked-consumer presentation assembly while preserving ranking and resource-evidence semantics.

### #44 Workload Analysis
Split configuration, mapping, quota, and presentation responsibilities while preserving tenant quota/resource mapping/governance semantics.

## Verification Strategy

Development uses #68 `KAORI Developer Check` for cheap path-aware feedback. Characterization/ownership contracts are added before structural extraction. Each family must retain focused report regression evidence and pass fresh code-health scanning before its exact-ledger entries are reconciled.

Only after the complete batch is review-clean:

1. freeze one final candidate;
2. run one fresh Full Admission;
3. merge to `kaori/staging` only after PASS;
4. reuse exact immutable evidence + Fast Smoke on staging;
5. stop at explicit human UAT.

No automatic promotion to `main` is authorized without explicit UAT acceptance.
