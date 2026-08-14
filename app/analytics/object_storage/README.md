# Object Storage Analytics Domain

`app/analytics/object_storage/` owns analytics semantics for provider-neutral
Object Storage systems. MinIO is the first qualified Object Storage provider and
Prometheus is the first operational metrics source; neither is the domain
contract.

## Evidence ownership

- Committed Object Storage Inventory is authoritative for current-state asset,
  bucket, quota, and configuration evidence.
- `MetricsSource` is authoritative for operational time-series observations used
  by Analytics.
- Alertmanager is optional for the current release and is reserved for alert
  lifecycle/correlation evidence.
- Analytics never reads MinIO credentials or creates MinIO clients.

## Package layout

```text
app/analytics/object_storage/
├── routes.py
├── service.py
├── runtime.py
├── dependencies.py
├── bucket_table.py
├── analysis.py
├── presentation.py
├── forecasting.py
├── materialization.py
├── job_adapter.py
├── tasks.py
└── sources/
    ├── resolver.py
    └── minio_prometheus.py
```

`service.py` orchestrates page evidence. `runtime.py` owns the provider-neutral runtime/readiness state machine and request-local fail-fast reader, while `dependencies.py` owns explicit blocking states. All three consume only the provider-neutral contract from `app.analytics.shared.metrics`. `analysis.py` owns pure domain calculations such as
capacity/performance/forecast posture, trend summaries, headroom derivation, and
Inventory-vs-operational reconciliation; it has no provider dependency. Provider-specific query syntax, response parsing,
and exception translation live in a pair-qualified adapter such as
`sources/minio_prometheus.py`. This prevents a Prometheus binding for another
Object Storage provider from accidentally receiving MinIO PromQL.

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
Prometheus currently maps them to PromQL via the Object Storage query profile. A
future CloudWatch/OpenTelemetry/etc. adapter must implement the same semantics
without changing the domain service or presentation contract. Prometheus adapters
for a different Object Storage provider use their own qualified metric profile.

## Metrics readiness contract

Operational metric discovery is owned by Prometheus binding validation, not by
page rendering. The source-owned Full Validation flow resolves the generic
`object-storage-metrics-v1` consumer profile to a provider-qualified validator.
For the current MinIO implementation that validator audits the `minio-v2`
profile by:

1. discovering scoped metric families in one Prometheus series request;
2. validating required label schema such as the bucket identity;
3. executing each registered canonical PromQL expression;
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

Background/materialization workloads may use a different retry policy; the UI
request path must not multiply an unreachable provider into a query storm.

## No-compatibility rule

The retired direct Prometheus domain modules (`metrics.py` and `parsing.py`) are
removed. Do not restore them as wrappers. Provider access belongs only to source
adapters and the domain service must stay provider-neutral.

## Analysis surfaces

The current Object Storage Analytics workspace exposes distinct operational semantics instead of reusing one generic summary for every route:

- **Overview** consolidates capacity, request-path, growth, and bucket-concentration posture.
- **Capacity & Usage** separates physical usable headroom, usage growth, bucket quota pressure, and concentration.
- **Performance** separates request demand from reliability, queue/inflight pressure, node availability, ingress/egress throughput, request/error history, and bucket request-path evidence. Increasing demand is descriptive; only error, waiting, and availability evidence drive request-path posture.
- **Top Consumers** ranks usage, object density, request demand, and error pressure independently.
- **Forecast** uses the current linear baseline only as a planning boundary and makes its methodology explicit.
- **Alerts & Anomalies** continues to provide metric-derived signals while Alertmanager lifecycle correlation remains optional.

Inventory reconciliation is intentionally non-authoritative: differences within the
selected thresholds are review evidence because Inventory and operational metrics have
different observation times. Analytics never rewrites Inventory from this comparison.


## UI readiness and record surfaces

Object Storage Analytics follows the same operational interaction contract as Kubernetes Analytics:

- scope changes use the shared KAORI HTMX loading bar and report the runtime state as `Checking Runtime` while the request is in progress;
- missing configuration, unvalidated required metrics, incomplete capability, disconnection, authentication failure, and total runtime-query failure are explicit blocking states;
- partial runtime-query failure is a degraded state, not a false healthy state;
- the Overview prioritizes operational KPI/posture, trend, consumer evidence, and drill-down workspaces before contract-readiness detail;
- bucket records use the shared Analytics record-pagination owner at `templates/analytics/components/_record_pagination.html`, with search, 5-row default pagination, 5/10/25/50 page sizes, HTMX partial refresh, and a header loading indicator.

The status words describe different evidence layers intentionally: `Ready` is persisted metric-contract validation, `Operational` is successful current runtime query execution, `Degraded` is partial current query success, and `Disconnected` is current transport failure. These terms must not be used interchangeably.

When a consumer binding still carries a retired validation profile, Analytics
reports `Consumer Validation Stale` instead of the ambiguous `Validation
Required`. The canonical consumer profile is `object-storage-metrics-v1`; the
MinIO-specific `minio-v2` contract is selected only by the provider-qualified
validator. Upgraded deployments reset the retired profile to consumer
validation required and must rerun validation with the current
`integration-validation` worker.

## Forecast materialization

Object Storage Forecast follows the Kubernetes Analytics worker pattern instead
of calculating long-range projections inside the interactive request. The
registered job `object_storage.forecast.materialize` runs on the dedicated
`forecasting` queue and materializes 7d, 30d, and 90d history windows into
`ObjectStorageForecastSnapshot` records.

The Forecast UI reads committed worker output and reports `Current`, `Stale`,
`Expired`, `Refreshing`, or worker-failure states from that artifact. The last
usable payload remains readable through the configured stale-grace period when
a refresh fails. Overview may consume the committed 30d forecast posture, but
it never executes a 30d range query in the browser request.

The worker resolves the same provider-neutral `MetricsSource` contract with a
background retry policy. A future non-Prometheus metrics adapter can therefore
materialize the same forecast artifact without changing Object Storage
Analytics domain code.
