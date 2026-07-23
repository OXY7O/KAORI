# Domain 3 — Kubernetes Inventory Persistence Atomicity

## Decision

A Kubernetes inventory refresh is one database transaction per cluster. Cluster metadata, nodes, namespaces, workloads, pods, services, ingress, storage, configuration, and resource quotas are committed together or rolled back together.

The canonical `KubernetesConnection` resolved by the worker is passed explicitly into the inventory persistence use case. Persistence must not recover a connection through `cluster.kubernetes_connection`, because that relationship is not the runtime authority and may be stale after admission.

## Transaction boundary

1. Resolve the canonical connection in the worker.
2. Pass the cluster and connection to `sync_inventory`.
3. Lock the cluster row for replacement serialization.
4. Collect and stage every inventory family using flushes only.
5. Commit once after all families succeed.
6. Roll back once when any family fails.

A failure during any collection or persistence stage preserves the previous committed snapshot. No partial new snapshot is visible.

## Validation

```bash
pytest -q \
  tests/kubernetes/test_inventory_persistence_atomicity.py \
  tests/contracts/kubernetes/test_inventory_persistence_atomicity_contract.py
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Restore the previous versions of:

- `app/inventory/synchronization.py`
- `app/integrations/kubernetes/adapter.py`
- `app/integrations/kubernetes/inventory.py`

No schema or data migration is involved.
