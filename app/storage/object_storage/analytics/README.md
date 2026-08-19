# Object Storage Analytics Domain

`app/storage/object_storage/analytics/` owns analytics semantics for provider-neutral
Object Storage systems. MinIO is the first qualified Object Storage provider and
Metrics Source is the only operational metrics category; concrete products are resolved by the source contract and are not part of the domain
contract.

## Evidence ownership

- Committed Object Storage Inventory is authoritative for current-state asset,
  bucket, quota, and configuration evidence.
- `MetricsSource` is authoritative for operational time-series observations used
  by Analytics.
- Alertmanager is the preferred active-alert source for Object Storage when an eligible consumer binding is available. Automatic source selection falls back to metric-derived alert-state evidence from the selected Metrics Source adapter when Alertmanager is unavailable.
- Analytics never reads MinIO credentials or creates MinIO clients.

## Package layout

```text
app/storage/object_storage/analytics/
├── routes.py
├── service.py
├── runtime.py
├── dependencies.py
├── bucket_table.py
├── alert_sources.py
├── alert_table.py
├── analysis.py
├── presentation.py
├── forecasting.py
├── materialization.py
├── job_adapter.py
├── tasks.py
└── sources/
    ├── resolver.py
    └── minio_metrics.py
```

`service.py` orchestrates page evidence. `runtime.py` owns the provider-neutral runtime/readiness state machine and request-local fail-fast reader, while `dependencies.py` owns explicit blocking states. All three consume only the provider-neutral contract from `app.common.analytics.metrics`. `analysis.py` owns pure domain calculations such as
capacity/performance/forecast posture, trend summaries, headroom derivation, and
Inventory-vs-operational reconciliation; it has no provider dependency. Provider-specific query syntax, response parsing,
and exception translation live in a pair-qualified adapter such as
`sources/minio_metrics.py`. This prevents a metrics binding for another
Object Storage provider from accidentally receiving the MinIO asset profile.

## Canonical metrics contract

Analytics asks for KAORI metric semantics such as:

```text
object_storage.capacity.total_bytes
object_storage.capacity.free_bytes
object_storage.usage.total_bytes
object_storage.usage.objects
object_storage.requests.rate
object_storage.requests.error_rate
object_storage.traffic.received_bps
```

The active source adapter translates those keys into its native query model.
The qualified asset adapter requests canonical metric expressions through `MetricsConsumer`; the selected Metrics Source backend owns protocol/query execution. A future backend may implement a different API or query language without changing the Object Storage service or presentation contract. Different Object Storage providers use their own qualified asset profiles.

## Metrics readiness contract

Operational metric discovery is owned by Metrics Source binding validation, not by
page rendering. The source-owned Full Validation flow resolves the generic
`object-storage-metrics-v1` consumer profile to a provider-qualified validator.
For the current MinIO implementation that validator audits the `minio-v2`
profile by:

1. discovering scoped metric families through the selected validation adapter;
2. validating required label schema such as the bucket identity;
3. executing each registered canonical metric expression;
4. classifying evidence as `ready`, `no_data`, `unsupported`, or `blocked`;
5. persisting the complete readiness snapshot on `IntegrationBinding.validation_evidence`.

Analytics reads that persisted snapshot through `MetricsSource.readiness`. It
does not rediscover metric families on every page request. Contract readiness
and current runtime reachability are intentionally separate: a previously
validated source can be reported as runtime-unreachable without destroying the
last known contract evidence.

Required metrics define the minimum operational contract. Recommended metrics
enrich health/performance/top-consumer analysis, while optional metrics (for
example bucket quota) never block the core contract when the provider does not
expose them.

## Interactive failure policy

Interactive Object Storage analytics is intentionally fail-fast:

1. The adapter executes provider calls with no interactive retry.
2. A transport or authentication error becomes a source-wide
   `MetricsSourceError`.
3. The request-local evidence reader opens its source circuit and skips all
   remaining provider queries for that page request.
4. Query-specific failures do not trip the source circuit; unrelated metrics may still render. If every runtime query fails, Analytics blocks with `Runtime Query Failed` rather than presenting an empty workspace.
5. Partial query success is reported as `Degraded`; successful runtime query execution is reported as `Operational`.
6. Committed Inventory evidence remains available when operational metrics are degraded or disconnected.

Background refresh workloads may use a different retry policy; the UI
request path must not multiply an unreachable provider into a query storm.

## No-compatibility rule

Retired direct provider/query-language domain modules are removed. Do not restore them as wrappers. Provider access belongs only to source
adapters and the domain service must stay provider-neutral.

## Analysis surfaces

The current Object Storage Analytics workspace exposes distinct operational semantics instead of reusing one generic summary for every route:

- **Analytics Overview** consolidates capacity, request-path, forecast, and consumer-concentration posture. Detailed bucket records stay in the owning drill-down workspaces instead of the Overview.
- **Capacity & Usage** separates physical usable headroom, usage growth, bucket quota pressure, and concentration inside Summary, Usage Trend, Quota & Buckets, and Evidence tabs.
- **Performance** separates request health, traffic/trend, bucket activity, and evidence into the shared Analytics tab workspace pattern. Request demand stays distinct from reliability, queue/inflight pressure, node availability, ingress/egress throughput, and request/error history; increasing demand is descriptive, while error, waiting, and availability evidence drive request-path posture.
- **Top Consumers** separates Storage Leaders, Request Activity, detailed Consumer Records, and Evidence. Ranking detail remains outside the Overview.
- **Forecast** separates Forecast Outlook, committed Usage Trend, Bucket Forecasts, Worker & Method, and Evidence. System and per-bucket linear baselines remain planning boundaries rather than capacity commitments; forecast-watch labels never impersonate active Alertmanager alerts.
- **Alerts & Anomalies** separates Alert Overview, provider Alert Records, Metric Signals, and Evidence. Automatic source selection prefers Alertmanager and falls back to metric-derived alert-state evidence from the selected Metrics Source adapter; metric-derived signals remain a separate KAORI operating-boundary evidence family.

Inventory reconciliation is intentionally non-authoritative: differences within the
selected thresholds are review evidence because Inventory and operational metrics have
different observation times. Analytics never rewrites Inventory from this comparison.


## UI readiness and record surfaces

Object Storage Analytics follows the same operational interaction contract as Kubernetes Analytics:

- dependency-blocked pages reuse the shared `components/dependencies/_blocker.html` readiness surface instead of maintaining a separate Object Storage blocker design; Object Storage pages use `Object Storage → Metrics`, while Alerts extends the path with `Alert Evidence`;
- a registered Object Storage system without `inventory_observed_at` is still blocked as `Object Storage Inventory Sync Required`; operational metrics do not bypass the committed inventory prerequisite;
- scope changes use the shared KAORI HTMX loading bar and report the runtime state as `Checking Runtime` while the request is in progress;
- missing configuration, unvalidated required metrics, incomplete capability, disconnection, authentication failure, and total runtime-query failure are explicit blocking states;
- partial runtime-query failure is a degraded state, not a false healthy state;
- the Overview prioritizes operational KPI/posture, trend, concise consumer concentration, and drill-down workspaces before contract-readiness detail;
- bucket records use the shared Analytics record-pagination owner at `templates/analytics/components/_record_pagination.html`, with 5-row default pagination, 5/10/25/50 page sizes, HTMX partial refresh, and a header loading indicator; active alert records additionally use auto-refreshing search/select filters and a conditional Clear Filters action with no horizontal table scroll.

The status words describe different evidence layers intentionally: `Ready` is persisted metric-contract validation, `Operational` is successful current runtime query execution, `Degraded` is partial current query success, and `Disconnected` is current transport failure. These terms must not be used interchangeably.

When a consumer binding still carries a retired validation profile, Analytics
reports `Consumer Validation Stale` instead of the ambiguous `Validation
Required`. The canonical consumer profile is `object-storage-metrics-v1`; the
MinIO-specific `minio-v2` contract is selected only by the provider-qualified
validator. Upgraded deployments reset the retired profile to consumer
validation required and must rerun validation with the current
`integration-validation` worker.

## Forecast worker refresh

Object Storage Forecast follows the Kubernetes Analytics worker pattern instead
of calculating long-range projections inside the interactive request. The
registered Job Configuration entry `object_storage.forecast.materialize` runs on
the dedicated `forecasting` queue and refreshes 7d, 30d, and 90d history windows
into `ObjectStorageForecastSnapshot` records. The same snapshot payload also stores bucket-level usage forecasts derived from bucket-labeled Metrics Source history, so per-bucket planning evidence does not require another job or database table. Buckets with fewer than two usable range samples stay visible as explicit history gaps instead of being omitted.

Forecast is intentionally the only Object Storage Analytics surface with a
scheduled Job Configuration entry. Overview, Capacity & Usage, Performance, Top
Consumers, and Alerts & Anomalies resolve current Metrics Source / Alertmanager
evidence at request time and combine it with committed Object Storage Inventory
where applicable; they do not maintain separate worker-owned snapshot artifacts.
Adding independent jobs for those surfaces would duplicate source queries and
create competing freshness ownership without a persisted artifact boundary.

The Forecast UI reads committed worker output and reports `Current`, `Stale`,
`Expired`, `Refreshing`, or worker-failure states from that artifact. The last
usable payload remains readable through the configured stale-grace period when
a refresh fails. Overview may consume the committed 30d forecast posture, but
it never executes a 30d range query in the browser request.

The worker resolves the same provider-neutral `MetricsSource` contract with a
background retry policy. A future Metrics Source backend can therefore
refresh the same forecast artifact without changing Object Storage
Analytics domain code.


## Bucket metric collection boundary

Bucket usage, object, quota, request, and error metrics are bucket-labeled operational evidence. KAORI queries the complete scoped bucket vector and performs ranking/pagination in the application; query profiles must not truncate the source vector with `topk`, because doing so can incorrectly turn lower-ranked buckets into apparent `N/A` records.

For MinIO v2, cluster and bucket telemetry are separate scrape categories. System capacity and S3-wide request metrics come from cluster metrics, while bucket usage/quota/request families require the bucket metrics endpoint. Full Validation records whether those optional/recommended families are actually present. Runtime rows then distinguish `Metric Not Scraped`, `No Current Samples`, `No Bucket Series`, and `Runtime Query Failed`; none of those states are coerced to zero. Committed Inventory is an allowed field-level fallback for bucket identity, point-in-time usage/object evidence, and quota state, but never for request-path rate or error-rate time series.

Quota semantics are also explicit: `Not Configured` is a successfully observed provider state and counts as quota-state evidence, while `N/A` is reserved for unavailable, unsupported, inconsistent, or not-collected quota evidence.


## Alert source contract

Object Storage Alerts & Anomalies keeps two different evidence families explicit:

1. **Provider alert records** use `Automatic`, `Alertmanager`, or `Metrics Source` selection. Automatic prefers the governed `object_storage_system` Alertmanager binding (`object-storage-alerts-v1`) and falls back to metric-derived alert-state evidence from the selected Metrics Source adapter. Alertmanager is lifecycle-rich; Metrics Source fallback is metric-derived rule-state evidence only.
2. **KAORI metric-derived signals** continue to evaluate Object Storage capacity, request error, queue-pressure, and node-health operating boundaries from the operational `MetricsSource`. These signals are not duplicated Alertmanager records and do not claim routing, silence, inhibition, or receiver evidence.

Alertmanager and Metrics Source are therefore independent evidence paths on the Alerts page. A Metrics Source outage must not suppress a usable Alertmanager alert stream, and an Alertmanager outage must not suppress usable metric-derived signals or Metrics Source alert fallback.
