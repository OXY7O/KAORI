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

## Package ownership for the current release

`app/analytics` is the canonical Kubernetes Analytics package for the current
release. Final recheck does not introduce a compatibility package, import shim,
or parallel `app/kubernetes/analytics` tree. Any future asset-first package move
must be an explicit direct-cutover architecture change with its own ADR and
migration plan; it is not an active release dependency.

The current boundary remains strict: this package owns Kubernetes-specific
analytics interpretation, while provider-neutral Prometheus and Alertmanager
adapters remain outside it. Cross-asset analytics must not be added here by
`asset_type` branching.

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

## UI system boundary

Kubernetes Inventory is the canonical KAORI workspace reference for Analytics.
Analytics may add charts, evidence interpretation, and domain-specific detail,
but it must reuse the same global palette, table primitives, filters, pagination
grammar, card geometry, empty states, and action hierarchy.

The reusable contract is documented in:

```text
docs/design/components/ANALYTICS_INVENTORY_UI_CONVERGENCE.md
```

Shared ownership belongs to `components/table_primitives.html`,
`components/table.html`, `components/pagination.html`, and the Analytics shared
components. Domain templates must not create local palette overrides or a
second table/pagination system.

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
Analysis is cluster-level and must not expose a node selector; node-level pressure belongs to Resource Utilization.

Storage Analysis uses mixed but explicit scope ownership: Cluster and Namespace remain top controls, Node is local to the Filesystem tab, PVC evidence follows Namespace, and PV evidence remains cluster-scoped. The cluster-scoped materializer collects every registered signal once, while `presentation.py` owns Namespace, Node, local filters, and independent pagination. PVC pressure is observed used bytes divided by observed volume capacity; requested capacity remains demand evidence. Missing domains remain Unknown/Limited and never become zero or Healthy. Storage uses one canonical `tab` parameter, renders a directly requested deep-link tab immediately, and lazy-loads only hidden Filesystem, PVC, and PV panels.

## Analytics presentation contract

- Use the shared KAORI `components/content_tabs.html` component and the native `analytics_controls.js` tab controller. Analytics must not keep an Alpine tab-state duplicate or a compatibility wrapper.
- Materialized snapshot decode is read-only and ORM-free: canonical cluster references carry id/name/environment/status in the committed payload; old payload shapes are refreshed rather than repaired through a database fallback.
- Forecast reprojection returns a freshly built canonical resource payload and does not preserve/remove obsolete derived keys from historical payloads.
- Capacity is the analytics snapshot-style baseline. Analytics Overview tabs and domain workspaces use the shared snapshot shell, header, metric strip, evidence surface, and interpretation primitives from `analytics/components/_analysis_surfaces.html`. Domain layouts may differ, but they must not fork the geometry or visual-role contract.
- Every requested Overview section declares its tracked load state. The compact progress strip counts only sections actually requested; composite OOB targets are marked loaded by the Health Summary response. The tracker runtime lives in `app/static/js/analytics_overview.js`, not an inline script.
- Snapshot section headers, actions, metric labels, status text, and empty-state titles use Title Case. Descriptive sentences and technical identifiers retain their natural casing.
- Resource utilization progress bars must receive resolved class strings, clamp width to 0–100%, and update from the committed snapshot percentage. Do not pass nested Jinja expressions inside a quoted macro argument.
- Top Consumers and Alerts & Anomalies Snapshot are always visible on the Overview page. They must not use `details`, chevrons, or expand/collapse state.
- Storage Snapshot and Trend Summary end with concise operational tips using the shared `components/detail_tip.html` treatment.
- Overview redesigns must preserve first-activation HTMX loading, selected cluster/time-range state, parameter-exact snapshot matching, and worker-first committed-snapshot boundaries.
- Analytics surfaces remain neutral for readability. Color is assigned by reusable role: Brand Violet for identity/navigation/actions, Insight cyan for explanation/methodology, Evidence slate for passive context, and semantic green/amber/red/slate only for actual operational state. All role geometry and colors are owned by `analytics/components/_analysis_surfaces.html`.
- Prometheus status and committed dataset metadata remain on neutral evidence surfaces. Dataset freshness exceptions use a neutral attention strip with a semantic warning glyph and compact badge rather than a full tinted panel.
- Pressure Posture and equivalent analytical context panels use neutral card surfaces and subtle outlines. Status is carried by a badge, semantic glyph, or quantitative bar instead of a full-card fill.
- Normalize all status tones through `table_label.semantic_tone(...)`. New presentation payloads use semantic tones; legacy color aliases are accepted only at the shared label boundary.
- Compact operational status uses `table_label.status_label(...)` without a Lucide icon. Dense repeated state columns use `status_indicator_label(...)` so the semantic dot improves scanning without adding decorative glyphs. Count/category metadata uses `metadata_label(...)`; count-only metadata remains iconless unless an icon conveys independent source or scope context.
- Every interpretation call declares a visual `role=` explicitly: `insight` for How To Read/methodology, `brand` for What To Do/review paths, `evidence` for passive context, and `status` only for actual operational state.
- Status-bearing utilization, pressure, risk, and headroom bars use `progress_bar.semantic_bar(...)`; composition, ranking contribution, loading, and materialization bars remain KAORI Violet.
- Category icons use `resource_icon_classes(...)`; domain templates must not duplicate Brand icon geometry or introduce local color maps.
- Analytics heroes use `page_hero.context_card(...)` or `context_card_body(...)` with exactly two metrics and one `Manage Clusters` action. Interpretation and attention messages belong below the hero in shared Analytics content surfaces.
- Final Lock v2 uses the precise `View Details` label for Analytics record-detail actions. Workload Request Fit/Runtime Demand, Top Consumer records, Alerts, and Anomalies keep dense evidence in the shared teleported record-detail modal rather than inline expansion.
- All eight Analytics domains own hero markup through dedicated hero partials; Forecast no longer keeps page-local hero geometry in `index.html`.
- Top Consumer summary cards render missing committed evidence as `No Evidence` / `N/A`; absent evidence must never look like a real consumer identity or a zero-valued operational signal.

## Analytics Overview runtime and evidence flow

- The full-page request resolves cluster scope only. It does not read every
  analytics dataset.
- `health-summary` is the single composite owner. It reads Prometheus readiness
  once, hydrates the seven committed datasets, builds snapshot coverage, health,
  action summary, and prioritized recommendations, then updates Hero Posture,
  Action Summary, and Recommendations through HTMX out-of-band swaps.
- Utilization, Capacity, Workloads, Storage, Consumers, Forecast, and Alerts tabs
  read their committed snapshot only on first tab activation. Hidden tabs must
  never issue initial requests.
- Overview snapshot freshness is parameter-exact. Capacity and Workload use the
  selected `time_range`; Forecast uses its normalized `history_window`; Alerts
  uses `source=auto`; cluster-scoped datasets match the selected `cluster_id`. A
  snapshot for another parameter variant is not counted as current.
- Domain snapshot adapters return `None` when committed evidence is unavailable.
  The Overview presenter owns the Unknown/N/A state. Missing evidence must never
  be projected as zero, Normal, Healthy, Low Risk, or No Alerts.
- Cluster Health can be Healthy only when all expected datasets are current and
  no known risk is present. Partial evidence produces Limited/Warning; absent
  evidence produces Unknown.
- Overview section endpoints are HTMX partial endpoints. Direct browser
  navigation redirects to the full Analytics Overview page. Responses use
  `Cache-Control: no-store` and vary on `HX-Request`.
- A newly observed Prometheus failure emits one operator-facing toast and one
  Activity Audit record per user session and failure fingerprint. Repeated
  refreshes of the same unresolved failure do not create notification noise.
- Drill-down links use the shared scoped-link helper so cluster/time-range
  parameters are appended with `&` when a destination already has a query string.
- Analytics Overview uses no web-process Redis/local result cache. Worker-owned
  committed snapshots are the only data cache and evidence boundary.

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

`app/analytics/alerts` owns Kubernetes alert and anomaly interpretation. Alertmanager
remains authoritative for routing, grouping, receivers, silences, inhibition, and
notification delivery. Prometheus supplies active-alert fallback and optional
restart/readiness anomaly evidence. KAORI reads those sources in the Analytics
worker, commits `analytics.alerts`, and serves web and report consumers from the
committed generation.

Local UI controls never change snapshot identity. The canonical snapshot dimensions
are only:

```text
cluster_id
source = auto | alertmanager | prometheus
```

Severity, status, Namespace, search, active tab, alerts page, anomalies page, and
each table's page size are presentation-only state.

## Canonical runtime flow

```text
Analytics worker
    ↓
Resolve Alertmanager and Prometheus bindings
    ↓
Collect active alerts and independent restart/readiness anomaly queries
    ↓
Normalize severity, status, Kubernetes identity, and ownership metadata
    ↓
Deduplicate HA replica and duplicate-scrape records
    ↓
Commit analytics.alerts for Cluster + Source
    ↓
Web/report readers load the committed snapshot
    ↓
Apply exact Namespace filter and independent local pagination
```

The report payload must not contact Alertmanager or Prometheus during report
rendering. Missing committed evidence produces an explicit unavailable report
context instead of synthetic zeroes.

## Canonical module ownership

| Module | Ownership |
|---|---|
| `application.py` | Worker orchestration, committed-context presentation, global posture, and operational composition. |
| `contracts.py` | Typed selection, pagination, source, normalized-record, and snapshot contracts. |
| `records.py` | Severity/status normalization, provider payload normalization, HA deduplication, and exact local filters. |
| `sources.py` | Alertmanager/Prometheus source reads, fallback policy, source status, and controlled provider errors. |
| `anomalies.py` | Independent restart/readiness collection, anomaly normalization, deduplication, and partial-evidence status. |
| `health.py` | Integration status, source health, and page summary semantics. |
| `routing.py`, `silences.py`, `inhibition.py` | Alertmanager routing and suppression interpretation. |
| `ownership.py`, `readiness.py` | Owner/runbook/contact evidence and incident-readiness scoring. |
| `signals.py` | Cluster signal overview and resource navigation. |
| `snapshots.py` | Analytics Overview projection and evidence-completeness posture. |
| `routes.py` | Full-page and HTMX-only transport boundary. |

PromQL is registered in
`app/integrations/prometheus/query_profiles/kubernetes_v1.py`; the expression
family is owned by `query_profiles/alerts_v1.py`. Domain modules do not embed
raw PromQL.

## Evidence semantics

Alert-source evidence and anomaly evidence are independent:

- Alertmanager may be connected while one Prometheus anomaly query fails.
- Prometheus fallback may provide alerts while Alertmanager routing and suppression
  evidence remains unavailable.
- Restart and readiness anomaly queries fail independently; one successful family
  remains visible when the other fails.
- `Healthy` or `Stable` requires connected alert evidence and complete anomaly
  evidence with no active signal requiring review.
- Partial or missing evidence is `Limited Evidence` or `Unknown`, never zero,
  Normal, or Healthy.

Prometheus anomaly queries only evaluate Pods in `Pending|Running`. Restart gauges
are normalized by `namespace,pod,container` before Pod aggregation. Alert records
prefer Alertmanager fingerprint identity and otherwise ignore Prometheus HA replica
labels when constructing canonical identity.

## Transport and table state

`/analytics/alerts` is the only full-page route. Alerts and Anomalies table endpoints
are fragment transports and require `HX-Request: true`; direct navigation redirects
to the canonical full page. Fragment responses are `no-store`, vary on `HX-Request`,
and push the full-page URL.

Alerts and Anomalies own independent pagination:

```text
alerts_page / alerts_per_page
anomalies_page / anomalies_per_page
```

Changing one collection must not reset or silently reuse the other collection's
page. Namespace matching is exact rather than substring-based.

## Cross-asset rule

Provider-neutral Alertmanager API behavior remains under `app/alertmanager`.
Kubernetes identity and workload interpretation remain in this package. Future
Server, HCI, or Storage alert analytics must consume provider-neutral records and
own their asset-specific enrichment separately; they must not add asset branches
to the Kubernetes workspace.

## Refactor priority across the current analytics package

The current service sizes show that the single-service-per-workspace pattern has
outgrown its original purpose:

| Workspace service | Approximate size | Priority |
|---|---:|---|
| `alerts/service.py` | 4,648 lines | Critical |
| `workload/service.py` | ~400 lines | Refactored |
| `top_consumers/service.py` | 2,158 lines | High |
| `forecast/service.py` | 2,157 lines | High |
| `overview/service.py` | 1,943 lines | High |
| `storage/service.py` | 1,553 lines | High |
| `utilization/service.py` | 1,172 lines | High |
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

Capacity Analytics is capability-gated through `PrometheusConsumer`. CPU, memory, and pod scheduling evidence uses one exact Ready-worker boundary: control-plane and legacy master nodes are excluded, and every allocatable, requests, limits, current usage, peak usage, and pod-placement signal is intersected with the Ready node condition. Request/limit validation requires the `node` label in addition to namespace, pod, resource, and unit.

`app/analytics/capacity/evidence.py` collects each provider signal once per materialization, `domain.py` owns calculation and risk semantics, `service.py` orchestrates the payload, and `presentation.py` normalizes display state. Missing evidence remains Unknown/N/A and is never synthesized as zero. Node Filesystem is an optional operational reference with `scheduling_resource=False`; it cannot determine scheduling posture or Capacity recommendations.

## Utilization capability contract

Utilization Analytics consumes Prometheus or Thanos only through `PrometheusConsumer` and requires instant query, range query, Kubernetes identity, utilization metrics, and canonical filesystem node identity. CPU, memory, and pod ratios use worker `kube_node_status_allocatable` denominators and exclude node roles matching `control-plane|master`; the numerator and top-consumer queries follow the same worker boundary. Node drill-down storage must use a canonical Kubernetes node label; `instance=IP:port` is not a supported identity fallback. Integration validation must report missing metrics or label remediation before the page is considered ready.

Missing or zero denominator evidence is not zero utilization. The canonical Utilization presenter returns `Unknown`/`N/A` and suppresses semantic progress when allocatable or filesystem capacity evidence is unavailable. Presentation strings, tones, trend labels, and posture values belong to `app/analytics/utilization/presentation.py`, not Jinja.


## Workload Analytics capability contract

Workload Analytics uses `PrometheusConsumer` and requires `instant_query`, `range_query`,
`kubernetes_identity`, `workload_metrics`, and `resource_requests_limits`. Provider-specific
fallback logic must not be implemented in the Analytics layer.

All request, limit, owner, QoS, current-usage, peak, and active-Pod count evidence is intersected
with Pods in `Pending|Running`. Container series are normalized with `max by(namespace,pod,container)`
before aggregation so duplicate scrape copies do not inflate values. ResourceQuota evidence retains
`namespace + resourcequota + resource + type`; multiple quota objects are evaluated independently.

Ownership is split by responsibility: `service.py` collects provider evidence and builds the committed
cluster/time-range payload; `quota.py` evaluates ResourceQuota objects; `mapping.py` evaluates workload
resource evidence; `domain.py` owns findings and aggregate posture; and `presentation.py` applies
Namespace, tab, local filter, and pagination state. Missing evidence is Unknown/Limited, never synthetic
zero or Healthy.

## Worker-Backed Materialization

Heavy Prometheus range queries are not executed independently for every web request. KAORI stores reusable results in `analytics_snapshots` and dispatches generation through the canonical job registry:

- `analytics.materialize` uses the `analytics-batch` queue for Capacity, Storage, Workload, Top Consumers, long-range Utilization trends, and the compact `dashboard.kubernetes.alerts` dataset.
- `analytics.forecast.materialize` uses the dedicated `forecasting` queue for all forecast range queries.
- Kubernetes Operations always retains the `24h` Capacity snapshot, one current Top Consumers snapshot, and the `30d` Forecast history required by dashboard consumers, even when an operator narrows optional materialization ranges.
- Forecast horizon and model are projected locally from committed history and never create additional worker queries or snapshot fingerprints. Resource tabs do not alter the committed payload.
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
- The full-page request resolves only the summary snapshot. Summary materialization must not query trend series, node selectors, all-node detail, or report-only tables.
- Trend and Node Detail are first-activation HTMX tabs. Pending polling begins only after activation and stops when the committed partial replaces the pending fragment.
- Direct access to a fragment endpoint redirects to the full workspace. HTMX fragments are `no-store` and vary on `HX-Request`.
- Multi-series trend charts expose a visible shared legend, align points by timestamp, preserve missing points as null, include dates for long windows, and render through `app/static/js/analytics_utilization.js` without a fixed 100% ceiling.
- Resource Utilization uses local filter/Trend/Node indicators and does not use the Analytics Overview composite tracker.
- See `docs/design/components/ANALYTICS_RESOURCE_UTILIZATION.md` and `docs/design/audits/KAORI_ANALYTICS_UTILIZATION_AUDIT_2026_08.md`.


## Workload Analysis presentation contract

Workload Analysis follows `docs/design/components/ANALYTICS_WORKLOAD_ANALYSIS.md` and the runtime audit in `docs/design/audits/KAORI_ANALYTICS_WORKLOAD_AUDIT_2026_08.md`. The committed snapshot is keyed only by Cluster and Time Range. Namespace, active tab, local filters, and pagination are presentation state.

The active deep-linked tab renders in the initial response; inactive Tenant Quota and Workload Mapping panels load once on first activation. Fragment endpoints require HTMX, are `no-store`, vary on `HX-Request`, and redirect direct navigation to the full page.

Request Coverage, Limit Coverage, QoS, Risk, and Analytics Evidence Coverage remain distinct signals. Current observations are labeled Current Usage; selected-window aggregates are labeled Selected-Window Pod Peak Sum. CPU and Memory request utilization remain separate. ResourceQuota object identity is visible and the controlling pressure/runtime boundary names its quota object. Right-sizing is deferred unless evidence is Complete. Aggregate Healthy requires complete tenant and workload evidence; empty or incomplete evidence is Unknown/Limited Evidence.


## Capacity Analysis Presentation

Capacity is a cluster-level Ready-worker fleet analysis. CPU, memory, and pods share the same Ready-worker denominator; Node Filesystem is a non-scheduling operational reference. The workspace uses shared Analytics surfaces, renders missing evidence as Unknown/N/A without progress, keeps progress fills KAORI Violet, preserves the selected tab across filter changes, separates governance findings from review navigation, and does not load a composite tracker or Chart.js runtime. See `docs/design/components/ANALYTICS_CAPACITY_ANALYSIS.md` and `docs/design/audits/KAORI_ANALYTICS_CAPACITY_AUDIT_2026_08.md`.


## Resource Forecast Presentation and Semantics

Resource Forecast uses Holt-Winters as the default model, with Linear Trend and Conservative Trend as explicit alternatives. The page does not expose a Resource Focus selector; CPU, Memory, Storage, Pods, Trend Analysis, and Recommendations are canonical tabs. Forecast evidence is labeled Latest Daily Average, Projected Horizon Value, Weekly Trend, and Historical Signal Quality. Signal Quality describes historical completeness and stability rather than forecast accuracy. Namespace CPU, Memory, and active Pods are compared with Ready-worker allocatable capacity; namespace Storage is compared with observed mounted-volume capacity. Unavailable evidence renders Unknown/N/A and is excluded from projected posture counts. The full page uses the tokenized interactive chart component and tab-visible lifecycle.


## Top Consumers presentation and snapshot contract

Top Consumers follows `docs/design/components/ANALYTICS_TOP_CONSUMERS.md` and `docs/design/audits/KAORI_ANALYTICS_TOP_CONSUMERS_AUDIT_2026_08.md`. Namespace is a materialized snapshot dimension; resource, search, priority, focus, sort, active tab, and pagination are presentation-only. A requested Namespace must match the committed payload scope exactly.

CPU and memory evidence includes only active Pods and normalizes duplicate container series before ranking. Pod pressure uses Ready-worker allocatable Pod capacity. PVC pressure uses observed mounted-volume capacity. Missing domain capability plus an empty query remains Unavailable rather than becoming confirmed zero or a false configuration gap. Ownership is split across `contracts.py`, `evidence.py`, `rows.py`, `domain.py`, `presentation.py`, `recommendations.py`, `service.py`, and `routes.py`. The table endpoint is HTMX-only and the unused `/top-consumers/section` compatibility surface is removed.

## Alerts & Anomalies Presentation Contract

The `analytics.alerts` workspace uses `/analytics/alerts` with canonical tab state for Alerts, Anomalies, Routing & Suppression, Ownership & Runbooks, Incident Readiness, Recommendations, and Operational Resources. Source readiness and committed worker snapshot evidence are separate boundaries. Partial optional evidence produces an incomplete or limited state rather than Healthy. Alert-domain payloads carry semantic levels and factual values only; shared Jinja components own status tones, record geometry, and pagination.


## Canonical Prometheus Readiness

All Prometheus-backed Analytics workspaces normalize provider observations through `app.analytics.common.presentation.present_prometheus_status` and render `analytics/components/_prometheus_status.html`. The card owns canonical Query Ready, Query Degraded, Unavailable, Not Configured, and Waiting for Cluster states plus Response and Checked At. Checked At always comes from the provider observation `last_checked_at`; materialization timestamps remain owned by Latest Data Snapshot.

## Resource Forecast runtime contract

Resource Forecast follows `docs/design/components/ANALYTICS_RESOURCE_FORECAST.md` and the runtime audit in `docs/design/audits/KAORI_ANALYTICS_FORECAST_AUDIT_2026_08.md`. The committed `analytics.forecast` snapshot is keyed by Cluster, History Window, and optional Namespace. Forecast Horizon, Model, and active Tab are local presentation state and never create additional worker queries.

CPU, memory, and active-Pod demand are scoped to Ready worker nodes and exclude `control-plane|master`. Duplicate container, Pod, node, and PVC series are normalized before aggregation. Storage compares PVC usage with observed mounted-volume capacity. Resource status uses the highest projected point inside the selected horizon; threshold ETA walks projected points from the latest observation and is bounded by that horizon. Low signal quality is Limited Evidence, never Healthy.

Forecast ownership is split across `contracts.py`, `calculation.py`, `resource.py`, `service.py`, `presentation.py`, and `routes.py`. `/analytics/forecast` is the only workspace route; the unused `/forecast/section` compatibility surface is removed. The chart aligns all resources to one timestamp axis and preserves missing observations as null.
