# KAORI Analytics Top Consumers Runtime Audit — August 2026

Status: Completed

## Scope

The audit covers `/analytics/top-consumers`, its HTMX record fragment, `analytics.top_consumers` materialization, Prometheus query definitions, Analytics Overview projection, report payload collection, templates, documentation, and regression contracts.

## Findings

1. Container usage, request, and limit series could be duplicated by multiple scrape targets.
2. Compute evidence did not consistently exclude terminal Pods.
3. CPU, memory, and Pod pressure denominators could include control-plane or NotReady nodes.
4. An empty request/limit query could be interpreted as a confirmed configuration gap even when the underlying capability was unavailable.
5. PVC pressure needed an explicit observed-volume denominator and duplicate-series normalization.
6. Namespace presentation could silently inherit a payload with a different snapshot scope.
7. The table fragment was directly navigable and cache semantics were unspecified.
8. The unused `/top-consumers/section` compatibility surface remained registered.
9. Hero posture collapsed Limited Evidence into generic Watch wording.
10. The report used a non-canonical mixed-resource sort value.
11. The service mixed query collection, row construction, risk logic, presentation, and pagination in one large module.

## Implemented Boundary

### PromQL

- CPU and memory series use `max by(namespace,pod,container)` before aggregation.
- Compute evidence is joined to `Pending|Running` Pod identity.
- Pod density counts distinct `Running` Pods.
- CPU, memory, and Pod capacity use Ready worker nodes and exclude `control-plane|master`.
- PVC usage and capacity use `max by(namespace,persistentvolumeclaim)`.
- PVC pressure uses `kubelet_volume_stats_capacity_bytes`; requested storage is not used.

### Evidence semantics

- Provider query errors remain explicit evidence errors.
- Advisory capability absence plus an empty result is Unavailable, not confirmed zero.
- Confirmed request/limit absence is only evaluated when its evidence query is authoritative.
- Missing totals or denominators suppress contribution and pressure ratios.
- Aggregate Healthy requires complete CPU, Memory, Pods, and PVC evidence.

### Snapshot and presentation

- Snapshot dimensions are Cluster plus optional Namespace.
- Resource, search, priority, focus, sort, tab, page, and page size are local presentation state.
- A requested Namespace must match the payload Namespace exactly.
- `/analytics/top-consumers/table` is HTMX-only, `no-store`, and pushes the canonical full-page URL.
- The unused section endpoint and navigation compatibility reference were removed.

### Clean-code ownership

```text
contracts.py     selection, schema, options, semantic constants
evidence.py      Prometheus collection and availability boundary
rows.py          identity, pressure, risk, and canonical row construction
domain.py        coverage, summary, posture, and payload schema
presentation.py  local filters, sorting, pagination, scope guard
recommendations.py actionable recommendation facts and cards
service.py       orchestration and snapshot projection
routes.py        full-page and HTMX transport
```

All Top Consumers runtime modules are below the 800-line KAORI module limit. The old service module and multi-argument row-builder debt entries were removed from the baseline rather than moved to an allowlist.

## Deployment

After deployment, refresh:

```text
analytics.top_consumers + cluster_id
analytics.top_consumers + cluster_id + namespace (for each materialized Namespace)
```

Old snapshots use payload schema version 2 and are rejected by schema version 3 until rematerialized.

## Validation

The focused contract suite validates:

- snapshot parameter ownership;
- HTMX-only transport and cache headers;
- removed legacy endpoint;
- duplicate-series normalization;
- query-profile registry validation: 161 total definitions, including 32 Top Consumers definitions;
- active-Pod and Ready-worker boundaries;
- observed PVC denominator;
- advisory capability semantics;
- exact Namespace scope matching;
- canonical report selection and `current` period semantics;
- bounded runtime module size.

Full application import tests require the Dev Container because the standalone audit environment does not provide Flask.
