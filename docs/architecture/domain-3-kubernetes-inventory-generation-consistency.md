# Domain 3 — Kubernetes Inventory Generation Consistency

## Purpose

Every inventory family produced by one Kubernetes refresh must expose the same `collected_at` generation timestamp. This lets KAORI prove that Cluster, Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, Configuration, and Resource Quotas belong to one committed refresh.

## Behavior

`sync_inventory()` creates one UTC timestamp before collection begins and passes it explicitly to every persistence function. Each inserted inventory row receives that timestamp. `ClusterInventory` remains the generation marker when a resource family is empty, because an empty family has no rows to stamp.

The existing single-transaction replacement remains authoritative: all families commit together or all changes roll back.

## Validation

```bash
pytest -q \
  tests/kubernetes/test_inventory_generation_consistency.py \
  tests/contracts/kubernetes/test_inventory_generation_consistency_contract.py
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Deployment

No schema migration is required. Existing rows retain their previous timestamps; the next successful refresh establishes a consistent generation.

## Rollback

Restore `app/inventory/synchronization.py` and `app/inventory/persistence.py`. No database rollback is needed.

## Changed files

- `app/inventory/synchronization.py`
- `app/inventory/persistence.py`
- `tests/kubernetes/test_inventory_generation_consistency.py`
- `tests/contracts/kubernetes/test_inventory_generation_consistency_contract.py`
