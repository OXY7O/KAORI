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
├── bucket_evidence.py
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

`service.py` owns two deliberately separate paths: worker collection and snapshot-only page assembly. `runtime.py` owns the provider-neutral readiness state machine and the fail-fast `EvidenceReader` used only while the analytics worker collects a snapshot, while `dependencies.py` owns explicit blocking states. `materialization.py` persists and reads the committed operational and forecast artifacts. All of these consume only the provider-neutral contract from `app.common.analytics.metrics`. `analysis.py` owns pure domain calculations such as capacity/performance/forecast posture, trend summaries, headroom derivation, and Inventory-vs-operational reconciliation; it has no provider dependency. Provider-specific query syntax, response parsing, and exception translation live in a pair-qualified adapter such as `sources/providers/minio/metrics.py`. This prevents a metrics binding for another Object Storage provider from accidentally receiving the MinIO asset profile.

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

The analytics worker reads that persisted readiness through `MetricsSource.readiness` when it builds a committed operational snapshot. Page requests read the readiness copy stored in that snapshot and never rediscover metric families or perform operational source probes. Contract readiness and collection-time runtime reachability are intentionally separate: a previously validated source can fail during a later worker refresh without destroying the last usable committed analytics artifact inside its stale-grace window.

Required metrics define the minimum operational contract. Recommended metrics
enrich health/performance/top-consumer analysis, while optional metrics (for
example bucket quota) never block the core contract when the provider does not
expose them.

## Worker collection and failure policy

Object Storage operational analytics follows the same materialization boundary as Kubernetes Analytics. Interactive page requests never query Metrics Source or Alertmanager for analytics evidence.

1. `object_storage.analytics.materialize` runs on the `analytics-batch` queue.
2. The worker resolves the validated Object Storage Metrics Source binding and uses one cached `EvidenceReader` collection for Overview, Capacity & Usage, Performance, Top Consumers, Alerts, and the current-range Forecast context.
3. A transport or authentication failure becomes a source-wide `MetricsSourceError`; the collector opens its source circuit and skips remaining operational metric queries for that work item.
4. Query-specific failures remain explicit evidence states. If every operational query fails, the worker rejects the refresh rather than committing an apparently empty healthy snapshot.
5. The worker also collects both Alertmanager and Metrics Source alert streams so `Automatic`, explicit Alertmanager, and explicit Metrics Source selection can be resolved later from committed evidence without provider access in the page request.
6. A successful collection is stored in `ObjectStorageAnalyticsSnapshot`. The UI reads only this committed artifact plus committed Object Storage Inventory and, where required, the separate forecast snapshot.
7. When the operational snapshot becomes stale, KAORI keeps the last usable payload inside the configured stale-grace window and queues an on-demand refresh. Missing or expired evidence blocks with `Object Storage Analytics Snapshot Required` until a worker commits usable data.

The registered job defaults to a 15-minute freshness interval with 24-hour stale grace. Its snapshot table is bounded by the unique `(object_storage_system_id, time_range)` scope: refreshes replace the current artifact instead of appending unbounded analytics history.

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

- dependency-blocked pages reuse the shared `components/dependencies/_blocker.html` readiness surface instead of maintaining a separate Object Storage blocker design; the readiness path is `Object Storage → Metrics → Analytics Snapshot`;
- a registered Object Storage system without `inventory_observed_at` is still blocked as `Object Storage Inventory Sync Required`; operational snapshots do not bypass the committed inventory prerequisite;
- scope changes use the shared KAORI HTMX loading bar and read the selected committed snapshot only; a stale or missing artifact queues an analytics worker refresh without turning the page request into a source query;
- missing configuration, unvalidated required metrics, incomplete capability, collection-time disconnection/authentication failure, and total worker-query failure are explicit states;
- partial worker-query failure is persisted as degraded evidence, not a false healthy state;
- the Overview prioritizes operational KPI/posture, trend, concise consumer concentration, and drill-down workspaces before contract-readiness detail;
- bucket records use the shared Analytics record-pagination owner at `templates/analytics/components/_record_pagination.html`, with 5-row default pagination, 5/10/25/50 page sizes, HTMX partial refresh, and a header loading indicator; active alert records additionally use auto-refreshing search/select filters and a conditional Clear Filters action with no horizontal table scroll.

The status words describe different evidence layers intentionally: `Ready` is persisted metric-contract validation, `Operational` records that the committed worker collection completed its operational queries successfully, `Degraded` records partial worker-query success, and `Disconnected` records a collection-time transport failure. Snapshot freshness (`Current`, `Stale`, `Expired`, `Refreshing`) is a separate artifact lifecycle and must not be conflated with source readiness.

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

Object Storage Analytics has two scheduled materialization owners, not one job per page:

- `object_storage.analytics.materialize` collects reusable operational metrics and both alert streams for Overview, Capacity & Usage, Performance, Top Consumers, Alerts & Anomalies, and current-range forecast context into `ObjectStorageAnalyticsSnapshot` on `analytics-batch`.
- `object_storage.forecast.materialize` performs long-range system and per-bucket forecast collection into `ObjectStorageForecastSnapshot` on the dedicated `forecasting` queue.

This separation prevents each page from repeating source queries while keeping heavier long-range forecasting independent from short-lived operational freshness.

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

For MinIO v2, cluster and bucket telemetry are separate scrape categories. System capacity and S3-wide request metrics come from cluster metrics, while bucket usage/quota/request families require the bucket metrics endpoint. Full Validation records whether those optional/recommended families are actually present. Committed worker rows distinguish `Metric Not Scraped`, `No Current Samples`, `No Bucket Series`, and `Runtime Query Failed`; none of those states are coerced to zero. Committed Inventory is an allowed field-level fallback for bucket identity, point-in-time usage/object evidence, and quota state, but never for request-path rate or error-rate time series.

Quota semantics are also explicit: `Not Configured` is a successfully observed provider state and counts as quota-state evidence, while `N/A` is reserved for unavailable, unsupported, inconsistent, or not-collected quota evidence.


## Alert source contract

Object Storage Alerts & Anomalies keeps two different evidence families explicit:

1. **Provider alert records** use `Automatic`, `Alertmanager`, or `Metrics Source` selection. The analytics worker stores both eligible streams in the operational snapshot. Automatic later prefers the committed Alertmanager stream and falls back to committed metric-derived alert-state evidence without querying either provider from the page request. Alertmanager is lifecycle-rich; Metrics Source fallback is metric-derived rule-state evidence only.
2. **KAORI metric-derived signals** evaluate Object Storage capacity, request error, queue-pressure, and node-health operating boundaries from the metrics collected in the same operational snapshot. These signals are not duplicated Alertmanager records and do not claim routing, silence, inhibition, or receiver evidence.

Alertmanager and Metrics Source remain independent evidence families inside the snapshot. A collection failure for one stream must not fabricate evidence for the other, and the UI preserves the committed fallback semantics until the next successful worker refresh.
