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

The rename should be a dedicated migration with compatibility imports and route
stability. This README establishes the target boundary now; it does not perform
the move.

## Source-of-truth rules

- Prometheus and kube-state-metrics are primary for utilization, capacity,
  request, limit, peak, headroom, placement, and overcommit calculations.
- Alertmanager is authoritative for Alertmanager alert state, routing result,
  inhibition state, and silence state that its API exposes.
- Kubernetes alert analytics consumes Alertmanager through the scope-based
  `app.alertmanager.service`/consumer facade. It must not instantiate
  `AlertmanagerClient` or read Alertmanager persistence models directly.
- Inventory data supplies identity and snapshot context only.
- Avoid live Kubernetes API fallback in analytics pages.
- Global or "All clusters" views use stored snapshot data; live metric and
  Alertmanager queries require a selected cluster or an explicit asset binding.
- Analytics enriches and interprets provider data. It does not replace
  Prometheus, Alertmanager, Thanos, or the Kubernetes API.

## Current directory responsibilities

| Path | Responsibility |
|---|---|
| `routes.py` | Registers the Kubernetes Analytics blueprint and connects overview and workspace endpoints to their route handlers. |
| `base/` | Contains legacy/shared Prometheus-oriented service behavior. New shared code should be placed here only when it is truly reusable by multiple Kubernetes analytics workspaces. |
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
├── queries.py
└── optional schema, normalizer, or presentation modules
```

This structure is a starting point, not a rule that all behavior must remain in
one `service.py`. When a service owns several distinct workflows or becomes hard
to navigate, split it by responsibility and use one orchestration entry point.

Shared metric/query behavior belongs in `base` or `common` only after repeated
use is demonstrated. Do not copy PromQL normalization, dependency-health
handling, pagination rules, or selected-cluster behavior across workspaces.

## UI and query contract

Supported time ranges are:

```text
1h, 6h, 12h, 24h, 7d, 30d, 60d
```

Use one HTMX loading indicator and preserve filter state across pagination and
refresh. Capacity Analysis must retain the agreed Cluster → Node selector
hierarchy.

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
Kubernetes cluster selection
        ↓
Resolve Alertmanager and Prometheus readiness
        ↓
Retrieve Alertmanager alerts and silences
        ↓
Retrieve Prometheus alert/anomaly series when required
        ↓
Normalize source-specific payloads
        ↓
Enrich with Kubernetes labels, namespace, resource, owner, runbook, and contact
        ↓
Build routing, silence, inhibition, ownership, and readiness summaries
        ↓
Filter and paginate operator-facing views
        ↓
Render Alerts & Anomalies and provide dashboard/report snapshots
```

## Files inside `app/analytics/alerts`

| File | Responsibility | Review |
|---|---|---|
| `queries.py` | Exposes Kubernetes alert and anomaly PromQL expressions through the versioned query-profile catalog. It is a compatibility layer, not the authoritative location of raw PromQL. | Correctly small. Keep query definitions in `app/prometheus/query_profiles/` and retain these exports only while existing imports require them. |
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
├── queries.py
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
└── service.py                # thin orchestration facade
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
8. Leave `service.py` as a compatibility facade while callers migrate.
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
3. Provide temporary compatibility modules under `app/analytics` that re-export
   the moved public APIs.
4. Keep public URLs and blueprint endpoint names stable during the first phase.
5. Move templates from `templates/analytics` to
   `templates/kubernetes/analytics` after route imports are stable.
6. Update versioned Prometheus query-profile domain keys and any persisted audit
   references in a controlled migration.
7. Remove compatibility imports only after all internal consumers and tests use
   the new path.

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
`PrometheusService` compatibility wrapper. New analytics code must declare the
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
executing a hidden compatibility fallback.

Filesystem PromQL returns the original series so identity labels remain
available. KAORI aggregates device series by the canonical node identity in the
consumer-facing storage service.
