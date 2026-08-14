# KAORI Analytics Storage Runtime Audit — August 2026

## Scope

The audit covers Kubernetes Analytics → Storage Analysis, its materialized dataset, Prometheus query profile, partial HTMX endpoints, Analytics Overview projection, Storage report payload, recommendation engine, templates, and static contracts.

## Material Findings

1. Filesystem size without available bytes could be converted into zero free space and false 100% pressure.
2. Duplicate node-exporter or kubelet series were summed for several signals.
3. PVC used percentage used requested capacity rather than observed volume capacity.
4. Aggregate and per-record provider queries duplicated work during one materialization.
5. Missing PVC evidence could produce zero free percentage and a Critical recommendation.
6. Lifecycle risk was not included consistently in Hero and aggregate posture.
7. Storage required both filesystem and PVC capabilities, blocking valid partial evidence.
8. Hidden tabs lost local filter/pagination state, and deep-linked tabs still rendered lazy placeholders.
9. Partial endpoints could be opened as complete pages and had no explicit no-cache boundary.
10. Jinja duplicated pressure thresholds and posture calculations.
11. The report described PVC usage against Requested Capacity.
12. Legacy service debt consisted of a 1,400+ line orchestration class and repeated provider helpers.

## Implemented Boundary

```text
Prometheus query registry
        ↓
StorageEvidenceCollector
        ↓
Storage parsing and domain evaluation
        ↓
cluster-scoped committed analytics.storage snapshot
        ↓
Storage presentation filters and pagination
        ↓
Page, Analytics Overview, recommendations, and report export
```

Canonical ownership:

- `app/analytics/kubernetes/storage/evidence.py` — one query per signal and query error representation.
- `app/analytics/kubernetes/storage/parsing.py` — label normalization and duplicate-series handling.
- `app/analytics/kubernetes/storage/domain.py` — pressure, lifecycle, availability, summaries, and posture.
- `app/analytics/kubernetes/storage/service.py` — materialization/context facade only.
- `app/analytics/kubernetes/storage/presentation.py` — tab, scope, local filters, pagination, and view model.
- `app/analytics/kubernetes/storage/routes.py` — full-page/fragment transport boundary.

## Accuracy Decisions

- `/var` is preferred only when a complete size/available pair exists; `/` is the fallback.
- Duplicate same-identity gauge samples use `max`, not `sum`.
- PVC pressure denominator is observed `kubelet_volume_stats_capacity_bytes`.
- Requested bytes remain demand evidence and never become pressure capacity.
- Missing denominators remain `None`/`N/A`.
- PVC/PV posture uses the highest lifecycle or pressure severity; one signal cannot mask a more severe signal.
- Healthy requires complete Filesystem, PVC, and PV domains.
- Observed empty inventories display zero rather than unavailable.

## UI and Transport Decisions

- Hero, Overview, and Capacity render domain-provided posture and tone.
- PVC panels show Requested, Observed Capacity, Observed Usage, and Remaining explicitly.
- Deep-linked Filesystem/PVC/PV tabs render immediately.
- Hidden heavy tabs hydrate once on first activation.
- Local filters and independent pagination are retained in lazy URLs.
- Cluster and Namespace filters preserve the active tab.
- Partial endpoints reject ordinary navigation by redirecting to the full page.
- Fragment responses are no-store and vary on `HX-Request`.

## Legacy and Debt Cleanup

Removed from the Storage service boundary:

- aggregate-total queries duplicated by per-record queries;
- repeated `PVC_INFO_QUERY`, `PV_INFO_QUERY`, and reclaim-policy queries;
- local Prometheus helper construction;
- service-owned filters and pagination;
- template-owned threshold/posture logic;
- the legacy `get_storage_capacity_summary` API.

Resolved Storage entries were removed from `docs/architecture/code-health-debt-baseline.json`. No new allowlist, compatibility wrapper, or debt-baseline exception was added.

## Validation Contract

The focused test set covers:

- incomplete filesystem evidence;
- `/var` to `/` fallback;
- observed-capacity PVC denominator;
- lifecycle-to-posture precedence;
- observed empty inventory semantics;
- Limited Evidence behavior;
- one-query-per-signal ownership;
- HTMX-only partial endpoints and cache headers;
- tab/filter/pagination state preservation;
- template threshold removal; and
- report denominator terminology.

Application-importing tests still require the project Flask dependency and must be rerun inside the KAORI Dev Container or production-equivalent build image.

## Deployment

The PromQL and snapshot schema changed. After deployment, rematerialize:

```text
analytics.storage + cluster_id
```

for each cluster, or wait for the scheduled Analytics materializer. Until replacement, old committed snapshots may retain the former requested-capacity denominator.
