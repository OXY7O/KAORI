# Kubernetes Analytics Domain

## Current purpose

`app/analytics` currently contains Kubernetes-only analytics. It converts
Prometheus, kube-state-metrics, Alertmanager, and Kubernetes inventory context
into operational views for:

- overview;
- utilization;
- capacity;
- storage;
- workload;
- forecast;
- top consumers; and
- alerts and anomalies.

Although the package is currently named `app.analytics`, its domain language,
data sources, models, query catalog, templates, and routes are Kubernetes
specific. It must not become a mixed folder containing Kubernetes, HCI, Server,
and Storage code separated only by conditionals.

## Naming and package decision

### Recommended target: `app/kubernetes/analytics`

The cleanest long-term structure is asset-first:

```text
app/
├── kubernetes/
│   └── analytics/
├── hci/
│   └── analytics/
├── server/
│   └── analytics/
└── <future-storage-asset-domain>/
    └── analytics/
```

This is preferred over `app/analytics/kubernetes` because:

1. Kubernetes is the bounded context and analytics is one capability inside it.
2. All Kubernetes concepts become discoverable under one package instead of
   being distributed across generic capability folders.
3. New asset domains can implement their own analytics without adding
   `asset_type` branching throughout shared services.
4. Kubernetes dashboards, inventory, operations, governance, and analytics can
   evolve together while retaining clear dependency direction.
5. Provider-neutral integration adapters such as `app/prometheus` and
   `app/alertmanager` remain separate from asset-specific interpretation.

Reserve a top-level `app/analytics` package only for future analytics that are
truly cross-asset, such as portfolio capacity, service-level correlation, or
cross-domain cost intelligence. Do not create a generic abstraction until at
least two asset implementations prove that the abstraction is genuinely shared.

### Why the package is not moved in this patch

The current package name is referenced broadly by application registration,
dashboards, reports, Prometheus query-profile domain keys, templates, tests, and
lazy module imports. A search currently finds hundreds of references. Renaming
it together with service decomposition would create a large, difficult-to-review
change.

The rename should be a coordinated direct cutover that updates imports, blueprint
registration, templates, tests, and persisted references in one controlled release.
Do not create an intermediate compatibility package. This README establishes the
target boundary now; it does not perform the move.

## Source-of-truth rules

- Prometheus and kube-state-metrics are primary for utilization, capacity,
  request, limit, peak, headroom, placement, and overcommit calculations.
- Alertmanager is authoritative for Alertmanager alert state, routing result,
  inhibition state, and silence state that its API exposes.
- Kubernetes alert analytics consumes Alertmanager through the scope-based
  `app.alertmanager.service` application boundary. It must not instantiate
  `AlertmanagerClient` or read Alertmanager persistence models directly.
- Inventory data supplies identity and snapshot context only.
- Avoid live Kubernetes API fallback in analytics pages.
- Web requests must read committed `AnalyticsSnapshot` generations. Prometheus
  and Alertmanager network calls belong to analytics or forecasting workers.
- Global or "All clusters" views use stored snapshot data. A selected cluster
  scopes the committed generation; it does not authorize a live web fallback.
- Analytics enriches and interprets provider data. It does not replace
  Prometheus, Alertmanager, Thanos, or the Kubernetes API.

## Worker snapshot request boundary

The Kubernetes Analytics request path is worker-first:

```text
Prometheus / Alertmanager
        ↓
Analytics or forecasting worker
        ↓
Committed AnalyticsSnapshot
        ↓
Web route and local presentation filters
        ↓
HTMX or full-page response
```

The browser request is not allowed to run a heavy provider query. Storage and
Top Consumers use one current committed snapshot because their previous time
range selectors did not alter the PromQL contract. Workload and Capacity retain
materialized time-range dimensions because those ranges change the worker query.
Forecast materializes historical windows only; forecast horizon, resource, and
method selectors reproject the committed history in the web process without
calling Prometheus again.

Snapshot fingerprints contain only provider-query dimensions. Pagination,
search, status, focus, and other presentation filters must never create a new
snapshot generation. A missing snapshot renders a stable pending page with the
same HTMX replacement ID as the requested workspace. Pending-page context must always define error, progress-message, and
progress-percent fields, even when no JobExecution has reported progress yet.
Determinate progress must use the same worker counters as the displayed
percentage; it must not use a decorative indeterminate bar. A dependency
failure renders a blocked state and must never be stored as a ready snapshot
payload.

Prometheus connection readiness and analytics feature readiness are separate
contracts. A Prometheus instance may be connected and generally Ready while a
specific analytics workspace is Capability Incomplete because exact metrics,
labels, range history, or request/limit evidence is missing. Module readiness,
source resolution, worker admission, and the workspace blocker must use the same
capability tuple as the owning analytics service.

## Current directory responsibilities

| Path | Responsibility |
|---|---|
| `routes.py` | Registers the Kubernetes Analytics blueprint and connects overview and workspace endpoints to their route handlers. |
| `base/` | Contains provider-neutral analytics contracts and shared orchestration used by multiple Kubernetes analytics workspaces. |
| `common/` | Owns Kubernetes analytics request parameters, selected-cluster context, cache helpers, common payloads, and shared base-service utilities. Avoid turning this folder into an unstructured dumping ground. |
| `overview/` | Builds the Kubernetes Analytics overview and lazy section payloads. |
| `utilization/` | Computes resource utilization and Kubernetes readiness/capacity usage context. |
| `capacity/` | Computes worker and node capacity, allocation, headroom, request/limit, and overcommit analysis. |
| `storage/` | Computes Kubernetes storage and PVC-related analytics. This is Kubernetes storage analytics, not KAORI artifact-storage backend behavior. |
| `workload/` | Computes namespace, workload, quota, placement, and resource configuration analytics. |
| `forecast/` | Produces Kubernetes resource trend and forecast context from time-series data. |
| `top_consumers/` | Ranks Kubernetes resource consumers using Prometheus and inventory context. |
| `alerts/` | Produces Kubernetes alert, anomaly, routing, silence, inhibition, ownership, and incident-readiness analytics from Alertmanager and Prometheus data. |

## Standard workspace structure

A workspace normally owns:

```text
<workspace>/
├── routes.py
├── service.py
├── optional domain contracts
└── optional schema, normalizer, or presentation modules
```

This structure is a starting point, not a rule that all behavior must remain in
one `service.py`. When a service owns several distinct workflows or becomes hard
to navigate, split it by responsibility and use one orchestration entry point.

Shared metric/query behavior belongs in `base` or `common` only after repeated
use is demonstrated. Do not copy PromQL normalization, dependency-health
handling, pagination rules, or selected-cluster behavior across workspaces.

## UI and query contract

Materialized time ranges for Capacity and Workload are:

```text
1h, 6h, 12h, 24h, 7d, 30d, 60d
```

Utilization trend uses its own hour-based snapshot dimension. Forecast history
uses `7d`, `30d`, and `90d`; its horizon selector is a local projection and does
not create additional worker snapshots. Storage and Top Consumers show current
snapshot scope and must not expose a time-range control that does not change the
provider query.

Use one HTMX loading indicator and preserve filter state across pagination and
refresh. A pending or blocked response must retain the page wrapper selected by
`hx-select` so the workspace never becomes a blank replacement. Capacity
Analysis must retain the agreed Cluster → Node selector hierarchy.

## Analytics presentation contract

- Use the shared Analytics content-tab component and `kaoriAnalyticsTabs`; do not maintain a separate Overview-only tab implementation.
- Capacity is the analytics snapshot-style baseline. Analytics Overview tabs and domain workspaces uses the shared snapshot shell, header, header icon, metric strip when applicable, bright evidence/context body, and darker interpretation/action region from `analytics/components/_analysis_surfaces.html`. Domain layouts may differ, but they must not fork the geometry or surface contract.
- Every lazy Overview section declares its tracked load state. The compact Overview progress strip reports completed or failed section requests and coexists with local skeletons and the filter-owned HTMX loading bar.
- Snapshot section headers, actions, metric labels, status text, and empty-state titles use Title Case. Descriptive sentences and technical identifiers retain their natural casing.
- Resource utilization progress bars must receive resolved class strings, clamp width to 0–100%, and update from the committed snapshot percentage. Do not pass nested Jinja expressions inside a quoted macro argument.
- Top Consumers and Alerts & Anomalies Snapshot are always visible on the Overview page. They must not use `details`, chevrons, or expand/collapse state.
- Storage Snapshot and Trend Summary end with concise operational tips using the shared `components/detail_tip.html` treatment.
- Overview redesigns must preserve lazy-section HTMX endpoints, selected cluster/time-range state, and worker-first committed-snapshot boundaries.
- Overview primary data, readiness, charts, metric grids, and side context panels use the bright `bg-surface-card` surface. `bg-surface-hover` is reserved for attention, interpretation, recommended-action, review-path, and execution-guidance strips through `analytics/components/_analysis_surfaces.html`.
- Prometheus status and committed dataset metadata remain bright; dataset freshness exceptions appear as a distinct darker attention strip below them.
- Pressure Posture and equivalent analytical context panels remain bright and use borders for separation.
- Normalize all status tones through `table_label.semantic_tone(...)`. New presentation payloads use semantic tones; legacy color aliases are accepted only at the shared label boundary.
- The Overview hero may use `page_hero.context_bottom_notice(...)` in the bottom action slot when the panel requires a short non-interactive attention message. Do not show a bottom notice and an action together.

## Analytics overview Prometheus status flow

- The overview shell validates cluster selection and Prometheus configuration
  only.
- Live connection health is owned by the dedicated `prometheus-status` lazy
  section.
- Do not run a separate Prometheus health check before every lazy overview
  section; this creates contradictory status and unnecessary load.
- A transient failure in one analytics query must be rendered in that section
  and must not replace unrelated sections with a page-level connection blocker.
- Overview section endpoints are HTMX partial endpoints. Direct browser
  navigation must redirect to the full Analytics Overview page.
- Keep inline Prometheus status concise. Low-level connection exceptions must
  not be rendered inside the status card.
- A newly observed Prometheus failure emits one operator-facing toast and one
  Activity Audit record per user session and failure fingerprint. Repeated lazy
  refreshes of the same unresolved failure must not create notification noise.
- Failure feedback uses normalized endpoint, category, and remediation context.
  The card only directs the operator to the toast or Activity Audit Log for
  details.

## Analytics dependency-state presentation

- Cluster, Prometheus, and alert-source blockers use the shared KAORI Violet
  dependency card in `components/dependencies/_blocker.html`.
- The inline card must show only the operator-facing title, a concise next-step
  description, dependency stage, and the permitted configuration action.
- Never append raw connection exceptions, request URLs, credentials, TLS traces,
  or client-library errors to the inline blocker.
- Preserve low-level failure context separately as `diagnostic_detail` so toast
  and Activity Audit flows can retain controlled diagnostic context.
- Setup states use warning semantics; unreachable or failed connection states
  use critical semantics. The containing surface, icon treatment, metadata
  labels, and action button remain KAORI Violet.
- Analytics hero posture cards use the same blocker wording and status semantics
  across Overview, Resource Utilization, Capacity, Storage, Workload, Forecast,
  Top Consumers, and Alerts & Anomalies.

# Kubernetes Alerts and Anomalies

## Purpose and boundary

`app/analytics/alerts` is the Kubernetes-specific alert analytics and
enrichment workspace.

Its purpose is to bring alerts already captured by Alertmanager into KAORI for:

- centralized visibility across multiple Kubernetes Alertmanager bindings;
- Kubernetes resource enrichment;
- source-health and fallback analysis;
- alert grouping and routing posture;
- silence and inhibition interpretation;
- ownership, runbook, and contact enrichment;
- incident-readiness scoring;
- Prometheus-derived Kubernetes anomaly signals; and
- downstream recommendations and operational context.

Alertmanager remains authoritative for alert routing and notification behavior.
This workspace does not replace Alertmanager. It interprets and enriches provider
data for Kubernetes operations.

This workspace is Kubernetes only. Future Server, HCI, or Storage alert analytics
must live in their own asset bounded context. They may reuse the provider-neutral
`app/alertmanager` adapter and later share proven canonical alert contracts, but
they must not add asset-specific branches to this package.

## Data flow

```text
Analytics worker resolves Alertmanager and Prometheus source contracts
        ↓
Retrieve Alertmanager alerts, silences, and Prometheus anomaly series
        ↓
Normalize and enrich Kubernetes identity, ownership, runbook, and contact data
        ↓
Commit `analytics.alerts` and `dashboard.kubernetes.alerts` snapshots
        ↓
Web request reads the committed generation
        ↓
Filter and paginate operator-facing views locally
        ↓
Render Alerts & Anomalies, dashboard sections, and report inputs
```

## Files inside `app/analytics/alerts`

| File | Responsibility | Review |
|---|---|---|
| PromQL query usage | `service.py` resolves stable query keys directly from `app.integrations.prometheus.query_profiles`; the alerts workspace does not own a duplicate query-export module. | Keep raw PromQL and version selection in the canonical provider query-profile catalog. |
| `routes.py` | Converts query-string filters into the alerts workspace context, enforces `analytics.view`, renders the full page, and renders HTMX alert/anomaly table partials or dependency blockers. | Approximately 89 lines and appropriately thin. `_context_from_request()` may later move to a typed request-parameter object, but no urgent split is required. |
| `service.py` | Currently owns pagination, cluster and namespace selection, Alertmanager and Prometheus loading, source fallback, payload normalization, filtering, anomaly generation, source health, routing summaries, silence matching, inhibition summaries, ownership enrichment, incident readiness, signal overview, full page context, and dashboard/report snapshots. | Approximately 4,648 lines, 69 functions, and several 170–288-line functions. This is a critical refactor target. It contains many cohesive subdomains that should be independently testable. |

The folder currently has no `__init__.py`. Imports work through Python namespace
package behavior, but package-marker conventions are inconsistent across
analytics workspaces. Standardize package markers during the dedicated package
migration rather than changing only one folder now.

## `service.py` refactor assessment

### Why it must be split

The problem is not only the number of lines. The file has multiple reasons to
change:

- filter or pagination behavior;
- Alertmanager payload schema changes;
- Prometheus query/result changes;
- routing/grouping presentation changes;
- silence matcher semantics;
- inhibition rules;
- ownership enrichment conventions;
- incident-readiness scoring;
- cluster signal overview presentation; and
- page/snapshot orchestration.

A change in any of those areas requires navigating and retesting one very large
module. Several functions exceed 170 lines, and
`build_selected_cluster_signal_overview()` is approximately 288 lines. This
reduces readability, makes isolated tests difficult, and encourages hidden
coupling through loosely typed dictionaries.

### Recommended target structure

After the package moves to `app/kubernetes/analytics/alerts`, use a structure
similar to:

```text
app/kubernetes/analytics/alerts/
├── __init__.py
├── routes.py
├── optional domain contracts
├── params.py                 # typed request/filter normalization
├── pagination.py             # AlertsPagination and page slicing
├── models.py                 # typed internal alert/silence summary contracts
├── sources/
│   ├── alertmanager.py       # Alertmanager reads and source status
│   └── prometheus.py         # Prometheus alerts and anomaly metric reads
├── normalization/
│   ├── alertmanager.py       # provider payload -> canonical alert
│   ├── prometheus.py         # Prometheus payload -> canonical alert
│   └── kubernetes.py         # resource/namespace/workload enrichment
├── anomalies.py              # restart/not-ready anomaly construction
├── routing.py                # receiver/group/routing summaries
├── silences.py               # matcher parsing, matching, and summary
├── inhibition.py             # inhibition interpretation
├── ownership.py              # owner/runbook/contact enrichment
├── readiness.py              # incident-readiness scoring
├── signals.py                # cluster and selected-cluster signal overview
├── snapshots.py              # dashboard/report snapshot contracts
└── service.py                # application orchestration and policy boundary
```

The target `service.py` should coordinate these modules and expose stable public
entry points such as:

```text
get_alerts_context(...)
get_alerts_snapshot(...)
load_alerts_by_source(...)
```

Consumers should not import internal normalizers or summary builders directly.

## Recommended refactor sequence for alerts

1. Freeze current behavior with characterization tests for Alertmanager and
   Prometheus source selection, filters, pagination, silence matching, routing,
   ownership, and snapshots.
2. Introduce typed internal contracts for normalized alerts, source status,
   pagination, and summaries. Preserve dictionary conversion at the template
   boundary initially.
3. Extract pagination and request-parameter normalization; these are low-risk and
   have few external dependencies.
4. Extract source readers and source fallback logic.
5. Extract Alertmanager and Prometheus normalizers, then move Kubernetes resource
   enrichment into its own module.
6. Extract routing, silences, inhibition, ownership, and readiness one at a time,
   each with focused tests.
7. Extract signal overview and snapshot builders.
8. Keep `service.py` as the public application boundary. Each entry point must own request policy, dependency composition, and result contracts; it must never become a pure pass-through module.
9. Move the package to `app/kubernetes/analytics/alerts` only after module
   boundaries and tests are stable.

Do not perform a mechanical 4,600-line move and a logical split in the same
commit. First establish module contracts, then migrate the package path.

## Cross-asset alert rules

- `app/alertmanager` owns provider/API integration and can be reused by multiple
  asset domains.
- Kubernetes alert enrichment belongs only in Kubernetes analytics.
- Server alert enrichment belongs in Server analytics.
- HCI alert enrichment belongs in HCI analytics.
- Storage alert enrichment belongs in the future Storage asset domain, not in
  the existing artifact-storage backend package.
- Cross-asset alert correlation, if introduced, should consume canonical alert
  records from each asset domain rather than importing asset-specific services.
- Provider integrations remain authoritative live sources; KAORI stores only the
  normalized history required for correlation, trends, reporting, and
  intelligence.

## Package migration plan

A safe migration from `app.analytics` to `app.kubernetes.analytics` should be a
separate technical initiative:

1. Add complete tests for blueprint registration, lazy overview imports,
   dashboard consumers, report consumers, and query-profile audit domains.
2. Create `app/kubernetes/analytics` and move one workspace at a time.
3. Update all internal imports and blueprint registration in the same cutover; do
   not leave re-export modules under `app/analytics`.
4. Keep public URLs stable only when they remain the canonical product contract;
   do not retain duplicate endpoint aliases.
5. Move templates from `templates/analytics` to
   `templates/kubernetes/analytics` in the same controlled change.
6. Update versioned Prometheus query-profile domain keys and any persisted audit
   references in an explicit migration.
7. Add CI assertions that the retired package paths and endpoint names do not
   return after the cutover.

## Refactor priority across the current analytics package

The current service sizes show that the single-service-per-workspace pattern has
outgrown its original purpose:

| Workspace service | Approximate size | Priority |
|---|---:|---|
| `alerts/service.py` | 4,648 lines | Critical |
| `workload/service.py` | 2,390 lines | High |
| `top_consumers/service.py` | 2,158 lines | High |
| `forecast/service.py` | 2,157 lines | High |
| `overview/service.py` | 1,943 lines | High |
| `storage/service.py` | 1,553 lines | High |
| `utilization/service.py` | 1,233 lines | High |
| `capacity/service.py` | 1,198 lines | High |

Refactor by cohesive responsibility and testability, not by arbitrary line
limits. As a practical review trigger, any module above roughly 800–1,000 lines
or any function above roughly 80–100 lines should be examined for multiple
reasons to change. These are review triggers, not hard coding rules.

## Consumer migration rule

Prometheus and Thanos reads must enter analytics through
`app.prometheus.consumer.PrometheusConsumer`, directly or through the temporary
canonical Prometheus consumer contract. New analytics code must declare the
capabilities required by a query when the requirement is more specific than the
base Instant Query or Range Query API.

Examples:

```python
consumer.query(
    query,
    required_capabilities=('instant_query', 'node_filesystem_identity'),
)
```

A page must not hide an integration contract failure by introducing an IP-based
or provider-specific query workaround. Missing metric labels, retention, or
identity mapping must be reported by integration validation and surfaced as a
capability blocker or degraded dependency state.

## Storage Analytics consumer contract

Storage Analytics is the first Kubernetes Analytics domain migrated to the
capability-aware consumer boundary. The page requires all of the following
before it loads live data:

- `instant_query`
- `kubernetes_identity`
- `pvc_usage`
- `node_filesystem_identity`

The filesystem contract accepts canonical `node`, `nodename`, or
`kubernetes_node` labels. It does not use `instance="IP:port"` as a node name.
When the contract is incomplete, the page renders an integration capability
blocker and directs the operator to Prometheus/Thanos remediation instead of
executing an unvalidated alternate query path.

Filesystem PromQL returns the original series so identity labels remain
available. KAORI aggregates device series by the canonical node identity in the
consumer-facing storage service.


### Capacity capability boundary

Capacity Analytics is now capability-gated through `PrometheusConsumer`. Worker allocatable, usage, node-role, pod-placement, and request/limit contracts must pass integration validation before the page, dashboard snapshot, or report section executes capacity queries.

## Utilization capability contract

Utilization Analytics consumes Prometheus or Thanos only through `PrometheusConsumer` and requires instant query, range query, Kubernetes identity, utilization metrics, and canonical filesystem node identity. Node drill-down storage must use a canonical Kubernetes node label; `instance=IP:port` is not a supported identity fallback. Integration validation must report missing metrics or label remediation before the page is considered ready. Presentation strings introduced while touching Utilization templates are prepared in Python rather than formatted in Jinja.


## Workload Analytics capability contract

Workload Analytics uses `PrometheusConsumer` and requires `instant_query`, `range_query`,
`kubernetes_identity`, `workload_metrics`, and `resource_requests_limits`. Namespace,
ResourceQuota, pod ownership, QoS, placement, requests/limits, and usage labels must pass
validation before the feature is available. Provider-specific fallback logic must not be
implemented in the analytics layer.

Templates touched by this feature consume presentation-ready counters, status metadata,
latency labels, and posture values from Python rather than deriving them in Jinja.

## Worker-Backed Materialization

Heavy Prometheus range queries are not executed independently for every web request. KAORI stores reusable results in `analytics_snapshots` and dispatches generation through the canonical job registry:

- `analytics.materialize` uses the `analytics-batch` queue for Capacity, Storage, Workload, Top Consumers, long-range Utilization trends, and the compact `dashboard.kubernetes.alerts` dataset.
- `analytics.forecast.materialize` uses the dedicated `forecasting` queue for all forecast range queries.
- Kubernetes Operations always retains the `24h` Capacity snapshot, one current Top Consumers snapshot, and the `30d` Forecast history required by dashboard consumers, even when an operator narrows optional materialization ranges.
- Forecast horizon, resource, and method are projected locally from committed history and never create additional worker queries or snapshot fingerprints.
- Alert-only clusters remain eligible for both `dashboard.kubernetes.alerts` and `analytics.alerts`; Prometheus-backed datasets are never scheduled for those clusters.
- Automatic policies are configured under **Platform Operations → Jobs & Executions → Job Configuration**.
- A stale successful snapshot remains readable during refresh or temporary Prometheus failure.
- Scheduled executions create `JobExecution` and `AuditEvent` records only; they do not create user notifications or toasts.
- Missing custom filter combinations are deduplicated and generated once on demand. The requesting web process never runs the heavy query.

### Protected refresh cadence

The default Analytics policy is inspected every 15 minutes and the Forecast
policy every 120 minutes. The scheduler dispatches only snapshots whose
freshness window has expired. Existing database policy values are not silently
overwritten by a new static default; operators should save a 15-minute
Analytics interval in Job Configuration after upgrading. KAORI applies minimum
cadence floors by data horizon:

- 24-hour analytics: at least 20 minutes
- 7-day analytics: at least 60 minutes
- 30-day analytics: at least 180 minutes
- 60-day analytics: at least 360 minutes
- 30-day forecast history: at least 120 minutes
- 90-day forecast history: at least 360 minutes

Manual execution intentionally refreshes all configured combinations. Scheduled Utilization trend work follows only the configured time ranges; a missing unconfigured trend can still be materialized once on demand. On-demand requests join an active fleet materialization when one exists, preventing a page request from duplicating work already running on the worker. Per-dataset stale-grace limits cap a broad policy value so alert snapshots cannot remain acceptable for the same duration as long-range analytics.

Analytics Overview reads committed database generations directly and does not add a second web or Redis TTL cache. This prevents a fresh worker commit from being hidden behind another presentation cache. Legacy `forecast_horizons` policy JSON is ignored and is removed the next time the Forecast policy is saved.

### Provider-pressure and failure contract

The worker does not run a separate analytics health request before the dataset
query. The selected dataset query is the authoritative runtime probe. A
previous unhealthy Integration Runtime observation remains visible as advisory
context, but it does not hard-block an eligible binding from being retried.

Heavy datasets acquire a lock for the selected Prometheus, Thanos, or
Alertmanager provider instance. This prevents Analytics and Forecast workers,
or multiple clusters sharing one endpoint, from overloading the same source in
parallel. Alert source `auto` acquires both Alertmanager and Prometheus locks
because anomaly candidates can use Prometheus while alert records use
Alertmanager.

Dataset priority, batch task limits, and isolated dataset timeouts are derived
from one catalog budget. Long horizons receive larger bounded budgets than
current/short queries. Transient connection and HTTP 429/500/502/503/504
failures receive bounded retries. Worker logs and committed snapshot metadata
record query fingerprints, query/retry counts, provider duration, source-lock
wait, and an explicit error code with remediation.

Failed refreshes never replace a previously committed payload with empty data.
Forecast, Top Consumers, and other provider failures propagate to the
materialization boundary. Alerts & Anomalies may remain partially available
when Alertmanager succeeds but optional Prometheus anomaly collection fails;
the partial-source warning is rendered explicitly.


## Resource Utilization presentation contract

- Use `analytics/components/_analysis_surfaces.html`; no Overview-only compatibility surface path may remain.
- Summary uses `analytics/components/_resource_pressure_lane.html` instead of duplicating four KPI cards.
- Trend and Node Detail are first-activation HTMX tabs. Pending polling begins only after activation and stops when the committed partial replaces the pending fragment.
- Multi-series trend charts expose a visible shared legend and render through `app/static/js/analytics_utilization.js`.
- Resource Utilization uses local filter/Trend/Node indicators and does not use the Analytics Overview composite tracker.


## Capacity Analysis Presentation

Capacity is a cluster-level Ready-worker fleet analysis. It uses the shared Analytics Analysis Surface and Resource Pressure Lane contracts, renders missing denominators as Unknown/N/A without progress, keeps progress fills KAORI Violet, separates governance findings from review navigation, and does not load a composite tracker or Chart.js runtime. See `docs/design/components/ANALYTICS_CAPACITY_ANALYSIS.md`.
