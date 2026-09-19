# Domain 3 — Kubernetes Fleet Inventory Consistency

## Problem

A fleet inventory job previously queried all clusters when the worker started and retained ORM rows throughout the loop. The effective target set could therefore differ from the set visible when the user admitted the job. Direct relationship access could also use a Kubernetes connection that was disabled or unbound while the job waited in Celery.

## Contract

KAORI snapshots an ordered list of cluster identifiers and display names during job admission. The exact snapshot is stored in the canonical job parameters/payload and passed to the worker.

For every target, the worker:

1. reloads the cluster by identifier;
2. resolves the canonical Kubernetes connection again;
3. runs inventory synchronization only when the target remains valid;
4. records per-cluster failure evidence when the cluster was deleted, unbound, disabled, or otherwise fails.

A newly registered cluster is intentionally excluded from an already admitted fleet job. A deleted or disabled target remains represented in the final result as a failed snapshot target rather than silently disappearing.

## Result semantics

- all targets successful: `succeeded`;
- some targets failed: `partially_succeeded`;
- all targets failed: the notification is an error while the canonical result retains complete per-target evidence.

The compatibility field `failed_clusters` is preserved. Structured `failure_evidence` adds cluster ID, snapshot name, exception type, and message.

## Validation

```bash
pytest -q \
  tests/kubernetes/test_fleet_inventory_snapshot.py \
  tests/contracts/kubernetes/test_fleet_inventory_consistency_contract.py

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Restore `app/kubernetes/cluster/sync_jobs.py` and `app/kubernetes/cluster/tasks.py` from the previous commit. No database migration or data rollback is required.
