# Kubernetes Analytics Worker Snapshot Boundary

## Purpose

This boundary prevents Kubernetes Analytics pages from issuing expensive
Prometheus or Alertmanager requests during a user-facing web request. Provider
queries are executed by the analytics or forecasting worker, committed to
`analytics_snapshots`, and reused by concurrent viewers until the configured
freshness window expires.

## Root causes corrected

### Connection readiness was confused with feature readiness

Prometheus connection state answers whether the configured endpoint and binding
are operational. It does not prove that every analytics feature has the exact
metrics, labels, or historical retention it requires.

The Storage and Workload readiness maps had drifted from their owning services:

| Workspace | Correct technical contract |
| --- | --- |
| Storage Analysis | `instant_query`, `kubernetes_identity`, `pvc_usage`, `node_filesystem_identity` |
| Workload Analysis | `instant_query`, `range_query`, `kubernetes_identity`, `workload_metrics`, `resource_requests_limits` |

Storage incorrectly required `range_query`, even though its current analysis did
not use a time-range query. Workload omitted Kubernetes identity and request/limit
evidence from the readiness presentation. The Prometheus module matrix and
materialization catalog retain the complete domain contract, while worker
admission enforces only the query transport required to collect runtime evidence.

A connected Prometheus source can therefore remain **Ready** while one workspace
is **Capability Incomplete**. Missing domain evidence such as storage identity,
workload ownership, or request/limit coverage is advisory to runtime collection:
the worker is allowed to execute the exact registered query when the binding can
perform the required instant or range operation. Operational Domain Readiness
continues to show the incomplete evidence, while the analytics page displays the
last committed snapshot and a concise readiness warning. Only missing query
transport, unusable runtime health, or missing binding setup is a hard blocker.

### Web routes still performed provider work

Several analytics workspaces built their full service context when the route was
opened or an HTMX partial was refreshed. That caused repeated provider queries
for concurrent users and made latency depend on Prometheus series cardinality,
Alertmanager response time, historical range size, and network health.

### Forecast HTMX replacement could become blank

The Resource Forecast form targets and selects `#forecast-page`. When a selected
history snapshot was missing, the generic pending response did not expose that
same wrapper ID. HTMX selected no element and replaced the workspace with an
empty response. Pending and blocked pages now preserve the requested page ID.

### Snapshot fingerprints included presentation filters

Search, pagination, active resource tab, status filters, forecast horizon, and
forecast model previously risked creating distinct materialization requests.
Those controls now operate on a committed context whenever they do not alter the
provider query.

## Final data flow

```text
Prometheus / Alertmanager
        ↓
Capability-aware worker admission
        ↓
Analytics or forecasting worker
        ↓
Committed AnalyticsSnapshot
        ↓
Route reads latest generation
        ↓
Local filtering, pagination, tab selection, and forecast projection
        ↓
Full page or HTMX partial
```

No analytics workspace may fall back to a live provider query from the web
request. A missing snapshot queues an on-demand materialization and returns a
stable pending state. A stale snapshot may remain visible while a refresh is
queued. A dependency blocker is shown as an operational state and is never
committed as ready analytics data.

## Workspace audit

| Workspace | Worker query dimension | Web-only dimensions | Provider source |
| --- | --- | --- | --- |
| Analytics Overview | Reads committed helper snapshots | Selected overview section | Prometheus and Alertmanager snapshots |
| Resource Utilization summary | Cluster | Display only | Prometheus |
| Resource Utilization trend | `trend_hours`, optional `trend_node` | Chart rendering | Prometheus |
| Resource Utilization node detail | `node` | Display only | Prometheus |
| Capacity Analysis | `time_range` | Presentation only | Prometheus |
| Storage Analysis | Current cluster snapshot | Namespace, node, search, status, storage class, pagination | Prometheus |
| Workload Analysis | `time_range` | Namespace, filters, pagination | Prometheus |
| Top Consumers | Optional namespace snapshot | Resource, focus, sort, search, pagination | Prometheus |
| Resource Forecast | `history_window`, optional namespace | Horizon, model, active resource tab | Prometheus |
| Alerts & Anomalies | `source` | Severity, status, namespace, search, pagination | Alertmanager or Prometheus |
| Kubernetes Operations Dashboard | Fixed compact snapshot consumers | Section rendering | Committed analytics snapshots |

## Canonical parameter rules

Snapshot fingerprints contain `cluster_id` plus only the dimensions listed in
the materialization catalog. Examples:

```text
analytics.storage
  cluster_id

analytics.workload
  cluster_id + time_range

analytics.top_consumers
  cluster_id + optional namespace

analytics.forecast
  cluster_id + history_window + optional namespace
```

UI-only values must not be stored in `parameters_json`. This prevents snapshot
explosion and lets many users share the same committed generation.

## Scheduling and freshness behavior

- Analytics policy ranges apply to Capacity, Workload, and Utilization Trend.
  The dashboard-required `24h` Capacity snapshot is retained even when that range
  is not selected.
- Storage and Top Consumers use current snapshots and do not expose time-range
  controls that would create no provider-query difference.
- Forecast policy materializes `7d`, `30d`, or `90d` historical windows. The
  `30d` dashboard history is always retained. Horizon and model are projected
  locally; CPU, Memory, Storage, Pods, Trend, and Recommendations tabs are presentation-only.
- Utilization Trend schedules only configured ranges. A missing range may be
  created once by an on-demand request.
- Freshness is range-aware and stale grace is capped by the owning dataset. A
  broad policy value cannot make five-minute alert data remain acceptable for a
  day.
- Alertmanager-only clusters receive both compact dashboard and full-page alert
  snapshots, but no Prometheus analytics datasets.

## Overview read path

Analytics Overview reads committed database generations directly. It does not
add a second web or Redis TTL cache over `analytics_snapshots`; otherwise a new
worker generation could remain invisible until the secondary cache expired.
Overview section endpoints hydrate only the requested snapshot-backed section.

## Failure and readiness behavior

1. No selected cluster: render the cluster dependency state.
2. No eligible provider binding or missing instant/range query transport:
   render setup/runtime guidance and do not queue work.
3. Connected source with incomplete domain evidence: queue materialization,
   retain the evidence gap as an advisory warning, and do not replace available
   data with a blocker.
4. Missing snapshot with executable dependencies: queue one exact,
   deduplicated worker materialization and render Pending.
5. Fresh snapshot: render immediately, including while current source readiness
   is temporarily degraded.
6. Stale snapshot inside grace: render stale data and queue a refresh.
7. Expired or invalid snapshot: render Pending until regenerated.
8. Builder returns a hard dependency blocker: fail the snapshot attempt. Never
   store the blocker as a ready payload.
9. One dataset exceeds its bounded execution time: mark only that snapshot
   failed and continue the remaining batch work items.

## Reliability guardrails

- Web routes never run Prometheus or Alertmanager provider queries.
- Missing snapshots persist a pending record before the builder starts, allowing the page to show the current JobExecution message and progress instead of an indefinite generic loader.
- Explicit cluster selection is authoritative. Without a cluster ID, KAORI
  prefers a cluster with a committed snapshot, then a source capable of the
  required query transport.
- A current provider outage does not hide an already committed snapshot. The
  page remains readable and displays a source warning.
- On-demand requests attach to an active fleet job only when that job contains
  the exact cluster, dataset, and canonical snapshot parameters. An unrelated
  fleet job can no longer leave a page polling forever.
- Analytics builders are bounded by `ANALYTICS_DATASET_TIMEOUT_SECONDS`; forecast
  builders use `FORECASTING_DATASET_TIMEOUT_SECONDS`. A timeout is isolated to
  one dataset and produces a partial batch result instead of freezing all
  following snapshots.
- Full domain capability evidence is still visible in Prometheus Operational
  Domain Readiness. It is not silently discarded or misrepresented as a source
  outage.

## Operational validation

After deployment:

1. Run Prometheus **Full Validation** so exact capability evidence is persisted.
2. Run **Analytics Data Refresh**.
3. Run **Forecast Data Refresh** after Analytics completes when the heavy-job
   per-user quota is one.
4. Confirm scheduled and on-demand jobs execute on `analytics-batch` and
   `forecasting` queues.
5. Confirm page selector changes do not cause Prometheus or Alertmanager network
   calls in the web container logs.
6. Confirm missing forecast history renders a Pending page and never a blank
   workspace.

## Rollback

Rollback the application commit and restart web, analytics worker, forecasting
worker, and Beat. No database migration is introduced. Existing snapshots remain
compatible; snapshots whose payload contains `dependency_blocker` are rejected
by this version and may be regenerated after rollback if the old behavior is
restored.
