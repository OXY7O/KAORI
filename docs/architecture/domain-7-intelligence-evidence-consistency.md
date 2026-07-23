# Domain 7 — Intelligence Evidence Consistency

## Decision

KAORI Intelligence may only derive inventory-backed recommendations from the committed inventory generation for each Kubernetes cluster.

The generation marker is `ClusterInventory.collected_at`. Inventory rows are eligible as recommendation evidence only when their `collected_at` equals that marker for the same cluster.

## Why

Inventory replacement is atomic, but historical or orphan rows may exist from older deployments, interrupted migrations, or manual recovery. Reading inventory tables without the generation boundary can produce stale recommendations after a newer refresh has already cleared the condition.

## Applied Boundary

The shared helper `filter_current_generation(query, model)` is applied to:

- mutable image findings from Pod inventory;
- unhealthy Pod phase findings;
- high Pod restart findings;
- Node readiness findings;
- Storage binding findings.

TLS certificate findings are not changed by this patch because they use the separate Governance TLS inventory lifecycle rather than the Kubernetes inventory generation contract.

## Operational Result

A recommendation now means the condition exists in the latest committed inventory snapshot. Old rows cannot keep a finding active after a clean refresh.

## Validation

```bash
pytest -q \
  tests/intelligence/test_current_generation_recommendations.py \
  tests/contracts/intelligence/test_domain7_current_generation_contract.py

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert the Domain 7 commit. No database migration is included.
