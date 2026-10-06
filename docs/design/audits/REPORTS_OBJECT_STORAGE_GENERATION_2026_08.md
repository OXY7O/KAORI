# Reports Object Storage Generation — Final Audit (2026-08)

## Decision

KAORI publishes the first two Object Storage report contracts only after the reporting pipeline supports a provider-neutral infrastructure asset scope end to end.

- Object Storage Inventory Report: XLSX default, CSV alternative.
- Object Storage Analysis Report: PDF default, CSV alternative.
- Analytics stays PDF + CSV across domains.
- Inventory stays XLSX + CSV across domains.

## Generic report scope

The persisted report boundary is now represented by `scope_asset_type`, `scope_asset_id`, and `scope_asset_label_snapshot`. Existing `cluster_id` and `namespace` remain for backward compatibility and Kubernetes-specific relationships.

Current canonical asset types:

- `kubernetes_cluster`
- `object_storage_system`

Generated artifacts, jobs, schedules, storage naming, report templates, and generated-report presentation consume the generic scope boundary. Existing Kubernetes report rows are backfilled by the migration.

## Object Storage Inventory

The inventory renderer reads only committed `ObjectStorageSystem` / bucket-or-container rows. Rendering does not issue provider API calls. XLSX and CSV therefore represent committed inventory evidence, not live provider state.

## Object Storage Analysis

The analysis collector combines:

- committed Object Storage inventory;
- validated metrics-source evidence;
- worker-materialized forecast evidence;
- provider-owned alert context.

Alert lifecycle ownership remains external. Missing live evidence is represented as a limitation rather than converted to a healthy or zero state.

## Publication boundary

`reports/catalog.yaml` is the executable report contract source. `reports/coverage.yaml` keeps the remaining roadmap candidates. Once the first two Object Storage contracts are registered, Object Storage coverage is `Published`; Forecast, Top Consumers, and Alerts & Anomalies remain candidates.

## UI ownership

Generate selects the infrastructure asset required by the report contract:

- Kubernetes report → Kubernetes Cluster + optional Namespace.
- Object Storage report → Object Storage System.

Schedules use the same scope contract and filter notification-channel eligibility by report domain. Generated Report pages render generic scope labels rather than assuming every artifact belongs to a Kubernetes cluster.

## Compatibility

Existing Kubernetes reports and schedules remain valid. `cluster_id`/`namespace` are retained, while the migration backfills generic scope identifiers for existing cluster-scoped rows. No runtime Object Storage state is copied into YAML.
