# Kubernetes Storage Inventory Alignment Audit — August 2026

## Scope

Reviewed collector, persistence, route, templates, relationship queries, topology, XLSX/CSV export, accessibility, code health, and obsolete-file reachability for StorageClass, PersistentVolume, and PersistentVolumeClaim inventory.

## Closed findings

- Split StorageClass, PV, and PVC API results into independent collection evidence.
- Limited non-fatal provider handling to HTTP 403/404 or unavailable client methods; server errors and unexpected generated-client `AttributeError` failures remain fatal.
- Removed persisted presentation dashes and preserved missing capacity/status as null evidence.
- Distinguished `allowVolumeExpansion=false` from a missing field.
- Distinguished classless/unbound/unassigned configuration from missing specification or status evidence.
- Added explicit specification, status, bound-capacity, requested-access-mode, and reported-access-mode evidence.
- Normalized both `dataSource` and `dataSourceRef` into one PVC data-source contract.
- Canonicalized lifecycle semantics, including deletion-aware `Terminating` and `Not Reported`.
- Prevented missing PVC or Pod collection evidence from appearing as zero relationships.
- Removed the silent 200-claim relationship cap and grouped PostgreSQL JSONB overlap by namespace.
- Corrected PVC detail so requested capacity is not reused as bound capacity.
- Reused canonical Pod operational posture in mounted-Pod previews.
- Refreshed Hero and Snapshot Context when Storage filters change.
- Removed Age from the compact table.
- Added caption, scoped headers, accessible filter labeling, and explicit empty-evidence copy.
- Updated XLSX/CSV and Topology to consume canonical Storage evidence.
- Removed the legacy `_inventory_scope.html` wrapper and added regression guards.

## Legacy cleanup

Deleted:

```text
app/templates/inventory/kubernetes/storage/partials/_inventory_scope.html
```

Storage now participates directly in the primary Inventory workspace tuple and does not use a route compatibility block.

## Database impact

No schema migration is required. Existing top-level Storage fields remain canonical searchable fields. Historical rows without the new JSON evidence flags intentionally render as `Not Reported` until the next Inventory Sync; no compatibility inference was retained.

## Verification boundary

Static, behavioral collector/export, PostgreSQL JSONB query compilation, Jinja, syntax, code-health, contract, topology, and patch-application checks are included. Live PostgreSQL, Kubernetes API, HTMX browser, responsive 14-inch, and dark-mode smoke tests remain deployment-environment checks.

## Validation result

- Focused Storage, Topology, and cross-export tests: `45 passed`.
- Kubernetes contracts: `208 passed`; two pre-existing failures remain in Secret choice-card styling and TLS schema-guard contracts outside Storage scope.
- Python syntax: `867` source files passed.
- Source hygiene: `1,854` tracked files passed.
- Test taxonomy: `205` modules passed.
- Storage Jinja parsing: `7` templates passed.
- Migration graph: `92` revisions, head `20260805_ingress_inventory_v2`.
- Node, Namespace, Workload, Pod, Service, Ingress, Storage, tabular export, canonical legacy-cleanup, and reviewed code-health verifiers passed.

The full quality gate cannot pass the runtime-import phase in the audit container because Flask is not installed. This is an environment limitation; it is not treated as a Storage runtime validation result.
