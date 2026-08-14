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
├── analysis.py
├── presentation.py
├── forecasting.py
└── sources/
    ├── resolver.py
    └── minio_prometheus.py
```

`service.py` orchestrates page evidence and consumes only the provider-neutral contract from
`app.analytics.shared.metrics`. `analysis.py` owns pure domain calculations such as
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
4. Query-specific failures do not trip the circuit; unrelated metrics may still
   render.
5. Committed Inventory evidence remains available when operational metrics are
   degraded.

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
- **Performance** combines request success, queue/inflight pressure, ingress/egress traffic, and separate request/error history.
- **Top Consumers** ranks usage, object density, request demand, and error pressure independently.
- **Forecast** uses the current linear baseline only as a planning boundary and makes its methodology explicit.
- **Alerts & Anomalies** continues to provide metric-derived signals while Alertmanager lifecycle correlation remains optional.

Inventory reconciliation is intentionally non-authoritative: differences within the
selected thresholds are review evidence because Inventory and operational metrics have
different observation times. Analytics never rewrites Inventory from this comparison.
