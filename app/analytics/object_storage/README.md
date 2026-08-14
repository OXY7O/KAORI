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
├── presentation.py
├── forecasting.py
└── sources/
    ├── resolver.py
    └── minio_prometheus.py
```

`service.py` consumes only the provider-neutral contract from
`app.analytics.shared.metrics`. Provider-specific query syntax, response parsing,
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
