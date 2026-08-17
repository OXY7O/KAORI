# Domain 3 — Kubernetes Canonical Sync Resolution

## Decision

Kubernetes inventory admission and worker execution must resolve the runtime connection through `app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver.connection_for_cluster`.

The `Cluster.kubernetes_connection` ORM relationship is persistence plumbing, not authorization to execute. It does not by itself prove that the canonical integration instance is enabled, bound as the selected primary source, or still eligible for runtime use.

## Behavior

Single-cluster admission obtains the shared resource lock, reloads the cluster, then resolves the canonical connection. If no eligible canonical binding exists, no `JobExecution` is created and nothing is sent to Celery.

Single-cluster and fleet workers resolve each connection again at execution time. A connection disabled or unbound after admission therefore fails closed instead of being used through a stale ORM relationship.

## Validation

```bash
pytest -q \
  tests/kubernetes/test_inventory_sync_canonical_resolution.py \
  tests/contracts/kubernetes/test_inventory_sync_canonical_resolution_contract.py
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert `app/cluster/sync_jobs.py` and `app/cluster/tasks.py` together with the tests and this document. No schema or data rollback is required.
