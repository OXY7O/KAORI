# Domain 3 — Kubernetes Final Stabilization

## Scope

This consolidation closes the Kubernetes foundation review before KAORI continues into Analytics. It combines canonical runtime authority, deterministic fleet targets, atomic persistence, generation consistency, and current-generation read boundaries.

## Runtime authority

Inventory admission and worker execution resolve Kubernetes connections through the canonical binding resolver. Direct ORM relationships are not runtime authority. Workers resolve again at execution time to fail closed when a connection is disabled, deleted, or unbound after admission.

## Fleet consistency

Fleet jobs persist a deterministic target snapshot at admission. Newly registered clusters do not enter an already-created job. Deleted or invalid targets remain visible in structured failure evidence and result in `partially_succeeded` where appropriate.

## Persistence and rollback

A cluster refresh uses one transaction. All inventory families are replaced and committed together. Any collection or persistence failure causes one rollback, preserving the previous committed snapshot.

## Generation consistency

One UTC `collected_at` generation is created for each refresh and assigned to ClusterInventory, Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, Configuration, and ResourceQuota rows.

ClusterInventory is the committed generation marker, including when a resource family is empty.

## Read boundary

Core inventory views apply `filter_current_generation()`. A row is visible only when its `collected_at` equals the ClusterInventory marker for its cluster. This prevents historical orphan rows or data left by an older deployment from being mixed into the current snapshot.

## Validation

Run:

```bash
pytest -q tests/kubernetes tests/contracts/kubernetes
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Deployment

No migration is required. Deploy application and worker code together. Run one inventory refresh per cluster after deployment so all rows use the unified generation contract.

## Rollback

Restore the files listed in PATCH_MANIFEST.md. No database downgrade is necessary. Existing inventory rows remain compatible because no schema changed.
