# Domain 4 — Prometheus Runtime Stabilization

## Decision

Prometheus source selection is an operation boundary, not a constructor-only decision.
KAORI resolves the eligible source again for every instant or range query using the
technical capabilities required by that operation.

## Runtime flow

1. Resolve a default source for status and backwards-compatible metadata.
2. At query execution, resolve candidates with `required_technical_capabilities`.
3. Select the highest-ranked eligible binding that has recorded capability evidence.
4. Build a client with that binding's scope selector.
5. Return the actual selected source in `ConsumerResult`, including `fallback_used`.
6. Fail closed when no bound source satisfies the operation contract.

This prevents a primary source without `range_query` from blocking a capable secondary
source and prevents analytics from executing against a source whose evidence does not
cover the requested operation.

## Validation lifecycle

The validation worker reloads the Prometheus instance immediately before provider I/O.
Disabled or non-active instances are rejected before network validation starts. This
protects delete/disable operations that happen after queue admission.

## Validation

```bash
pytest -q \
  tests/prometheus/test_capability_aware_source_selection.py \
  tests/contracts/prometheus/test_domain4_prometheus_runtime_contract.py

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert `app/prometheus/consumer.py` and the Prometheus guard in
`app/integrations/validation/tasks.py`. No database migration is required.
