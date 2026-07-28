# Kubernetes Analytics Materialization Reliability Audit

Date: 2026-07-28  
Scope: Kubernetes Analytics scheduler, Job Configuration, Celery workers, Prometheus/Thanos and Alertmanager consumers, snapshot materialization, worker logging, and operator-facing readiness/error states.

## Executive Summary

The repeated `Unavailable` or `Disconnected` condition was not evidence that Prometheus was always down. The reviewed code had several conditions that could create false negatives or amplify temporary provider pressure:

1. Analytics performed a lightweight Prometheus health query before the real dataset query. A transient failure in that extra request could block materialization even when the real dataset query would have succeeded.
2. A previous unhealthy runtime observation was treated as a hard worker admission blocker. One timeout could therefore keep a later execution unavailable until another runtime observation changed the stored state.
3. Analytics and forecasting workers could query the same Prometheus or Thanos endpoint concurrently, including clusters sharing one endpoint.
4. A large manual refresh could contain many clusters and time ranges while retaining a fixed global deadline.
5. A 60-day range could inherit the same isolated dataset deadline as a short or instant query.
6. Some query helpers converted provider failures into empty values. The resulting snapshot could appear valid while data was actually unavailable.
7. Alertmanager data could succeed while optional Prometheus anomaly queries failed silently.
8. Worker and UI errors were too generic to distinguish timeout, authentication, overload, capability, query, dispatch, and source-contention failures.

The implementation now treats the dataset's real query as the authoritative runtime probe, limits concurrent heavy work by selected provider, applies horizon-aware budgets, retries bounded transient failures, preserves the last successful snapshot, and surfaces a structured failure contract in worker logs, Job Configuration, and analytics pages.

## Expected Runtime Contract

```text
Celery Beat / Manual Run / On-Demand Request
                    ↓
        Canonical JobExecution record
                    ↓
       Analytics or Forecasting worker
                    ↓
   Provider-scoped query concurrency boundary
                    ↓
       Prometheus / Thanos / Alertmanager
                    ↓
       Committed AnalyticsSnapshot generation
                    ↓
     Every Kubernetes Analytics web workspace
```

Web routes read committed snapshots. Page filters do not run heavy Prometheus queries. A missing or expired generation dispatches or joins a worker execution. A stale successful snapshot remains usable while a refresh runs or while a temporary provider failure is investigated.

## Findings and Corrections

### 1. Duplicate health query before real analytics work

**Finding**

Analytics status used an additional `vector(1)` query before the registered dataset builder ran. This created an extra provider request and allowed a transient health timeout to prevent the actual query.

**Correction**

- Removed the analytics-specific health-query profile entry.
- `PrometheusConsumer.analytics_status()` evaluates binding and query-transport eligibility without making a network call.
- The real dataset PromQL request is now the authoritative runtime probe.
- Generic Integration Runtime validation may still use `vector(1)`; that is expected and remains separate from analytics materialization.

### 2. Stored unhealthy observation blocked later worker attempts

**Finding**

A stored state such as `unhealthy`, `failed`, or `disconnected` could block the next worker execution even when the binding, endpoint, and query transport remained eligible.

**Correction**

- Persisted runtime health is advisory during worker admission.
- The UI can still show that the previous observation was degraded.
- Materialization retries the actual dataset query and records the new authoritative result.
- Binding disabled, validation incomplete, missing selector, missing query transport, and missing source remain hard blockers.

### 3. Shared provider overload from parallel workers

**Finding**

The analytics worker and forecasting worker use separate queues. Two clusters can also share one Thanos/Prometheus endpoint. Without a shared concurrency boundary, independent executions could submit heavy range queries to the same provider simultaneously.

**Correction**

- Added provider-scoped advisory locks.
- Prometheus locks use the selected provider instance, not only the cluster ID.
- Alert source `auto` acquires both selected Alertmanager and Prometheus locks because alert materialization can collect Alertmanager records and Prometheus anomaly candidates in one dataset.
- Locks are acquired in deterministic order to avoid lock-order inversion.
- Unrelated provider instances can still run concurrently.
- Source-lock wait time is recorded in snapshot telemetry and worker logs.

### 4. Fixed batch deadline for variable work volume

**Finding**

A manual execution can refresh every configured cluster/range combination, but task limits did not scale adequately with the number and horizon of work items.

**Correction**

- Dataset definitions now declare execution priority and expected task budget.
- Current/short datasets run before long trends and forecasts.
- Batch soft and hard limits scale with admitted work, within bounded maximums.
- Celery visibility timeout was increased so a long acknowledged task is not redelivered while still executing.
- Scheduled executions continue to dispatch only due snapshots; manual execution intentionally processes all configured combinations.

### 5. Long range inherited a short isolated timeout

**Finding**

The isolated dataset timeout used one fixed analytics value. A 60-day trend could therefore be terminated at the same deadline as a short query even though the catalog already assigned a larger expected budget.

**Correction**

- Added one shared `dataset_task_budget_seconds()` contract in the materialization catalog.
- Both batch admission and isolated dataset timeout use the same horizon-aware estimate.
- Long time ranges receive a larger bounded deadline; instant/current datasets remain constrained.
- This removes duplicated budget logic from the job adapter.

### 6. Repeated client construction and unbounded transient behavior

**Finding**

Provider clients could be rebuilt repeatedly within one dataset, and transient provider responses were not retried consistently.

**Correction**

- Prometheus clients are created lazily and cached per provider/binding/timeout within one consumer.
- The HTTP client uses a reusable `requests.Session`.
- Connection errors and HTTP 429/500/502/503/504 responses receive bounded exponential-backoff retries.
- Defaults: 2 retries with 1-second base backoff.
- Query text is not persisted; bounded SHA-256 fingerprints are logged for correlation.

### 7. Silent empty data after provider failure

**Finding**

Some Forecast and Top Consumers paths swallowed provider exceptions and returned empty arrays or zero values. This could create a technically successful snapshot with unavailable data.

**Correction**

- Provider failures propagate to the materialization boundary.
- A failed generation is marked failed with a structured error.
- The previous committed payload is preserved instead of overwritten with an empty result.
- The page shows stale data plus the latest refresh failure and recommended action.

### 8. Optional alert anomaly failure was invisible

**Finding**

Alertmanager records could remain available while Prometheus anomaly candidates failed. The optional failure was converted to an empty anomaly list without operator feedback.

**Correction**

- Alert materialization records a partial-source status.
- The Alerts & Anomalies UI shows that alerts remain available while Prometheus anomaly candidates are unavailable.
- Worker logs include the provider error and query telemetry.

### 9. Generic failure messages

**Finding**

A generic failed state did not tell an operator whether the cause was provider timeout, overload, authentication, source contention, missing capability, invalid PromQL, queue dispatch, or an internal transform error.

**Correction**

Worker failures now use explicit codes:

| Code | Meaning | Typical operator action |
|---|---|---|
| `provider_timeout` | Prometheus/Thanos did not complete before timeout | Review query saturation, slow queries, CPU/memory, then retry or tune range timeout |
| `provider_overloaded` | HTTP 429 or transient 5xx from provider | Reduce concurrent/heavy ranges and inspect provider capacity |
| `provider_connection_failed` | DNS/network/TLS endpoint failure | Validate routing, DNS, TLS, and endpoint availability |
| `provider_authentication_failed` | Credentials rejected | Correct credentials and rerun validation |
| `promql_query_failed` | Provider rejected the query | Use logged fingerprint and validate metrics/labels/profile compatibility |
| `source_busy` | Another analytics workload held the provider slot | Wait for current execution, then retry |
| `dataset_timeout` | One dataset exceeded its isolated or task budget | Reduce ranges or tune provider/task capacity after review |
| `analytics_dependency_unavailable` | Source/binding/capability is not eligible | Review Integrations scope, validation, and readiness evidence |
| `dispatch_failed` | Job could not be queued | Review Redis/Celery/web logs and queue availability |
| `analytics_materialization_failed` | Internal builder/transform failure | Review full worker traceback and snapshot failure metadata |

The same title, detail, remediation, job ID, queue, query count, retry count, provider time, and source-lock wait are available where applicable in logs or UI.

## Data Availability by Workspace

| Workspace | Worker dataset strategy |
|---|---|
| Analytics Overview | Reads committed generations and summary snapshots; no heavy web query |
| Resource Utilization | Current summary, optional node detail, and trend snapshots |
| Capacity Analysis | Time-range-specific capacity snapshots |
| Storage Analysis | Shared current storage snapshot |
| Workload Analysis | Time-range-specific workload snapshots |
| Resource Forecast | Dedicated forecasting worker and history-window snapshots |
| Top Consumers | Shared current snapshot; presentation filters remain local |
| Alerts & Anomalies | Alertmanager/Prometheus snapshot with explicit partial-source warning |

## Default Operating Values

| Setting | Default after correction | Purpose |
|---|---:|---|
| Analytics Data Refresh policy | 15 minutes | Refresh current datasets before their 15–20 minute freshness boundary |
| Forecast Data Refresh policy | 120 minutes | Refresh forecast history independently |
| Analytics worker concurrency | 2 | Allows independent providers to run while provider locks serialize shared endpoints |
| Forecasting worker concurrency | 1 | Limits expensive long-history work |
| Instant query timeout | 30 seconds | Bounds normal instant queries |
| Range query timeout | 120 seconds | Bounds one provider range request |
| Analytics source-lock wait | 900 seconds | Allows queued heavy work to wait rather than overload a provider |
| Analytics dataset baseline timeout | 300 seconds | Minimum per-dataset budget; long horizons scale upward |
| Forecast dataset baseline timeout | 600 seconds | Minimum forecast dataset budget |
| Analytics maximum soft limit | 7,200 seconds | Bounded large fleet/manual execution |
| Forecast maximum soft limit | 14,400 seconds | Bounded long-history forecast execution |
| Celery visibility timeout | 18,000 seconds | Prevents premature redelivery of long acknowledged tasks |

Changing static defaults does not overwrite an existing database policy. After deployment, open **Platform Operations → Jobs & Executions → Job Configuration → Analytics Data Refresh** and save the intended interval. Recommended operational interval: **15 minutes**.

## Prometheus/Thanos Capacity Review

The code audit can distinguish false blocking and query-pressure behavior, but it cannot prove the current provider has sufficient CPU or memory without runtime metrics. Review the provider when `provider_timeout`, `provider_overloaded`, repeated retries, or high source-lock wait appears:

1. Container/pod CPU throttling and memory/OOM history.
2. Prometheus/Thanos Query concurrent-query limits and queue length.
3. Slow-query log entries correlated with the logged query fingerprint and job timestamp.
4. Query engine duration, sample volume, and range-query cardinality.
5. HTTP 429, 503, and 504 responses from provider, ingress, proxy, or load balancer.
6. Retention and long-range availability for 30/60/90-day queries.
7. Shared Thanos Query use across multiple clusters and other external consumers.

Do not increase timeouts first without checking these signals. A larger timeout can hide saturation while keeping provider resources occupied longer.

## Removed or Consolidated Compatibility Code

- Removed analytics-specific `vector(1)` health-query profile entry.
- Removed eager/duplicate Prometheus client construction from cluster-scoped service paths.
- Consolidated range-budget calculation in the materialization catalog.
- Removed silent provider-error fallbacks that produced empty Forecast/Top Consumers data.
- Removed the unused live multi-cluster alert comparison builder, its query wrapper, and its orphaned TypedDict contract; Analytics pages continue to use committed alert snapshots.
- Kept serialization compatibility only where required to read older committed snapshots; this is an active data-compatibility boundary, not a live provider fallback.

## Deployment and Verification

Restart services that load changed web, worker, or scheduler code:

```bash
docker compose -f compose.production.yml restart \
  web analytics-worker forecasting-worker maintenance-worker beat
```

Verify queues and workers:

```bash
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=200 analytics-worker
docker compose -f compose.production.yml logs --tail=200 forecasting-worker
```

Run Analytics Data Refresh manually once after deployment and verify:

1. Job Configuration progresses from queued/running to terminal without reload.
2. Recent Executions shows succeeded or partial status and clear failure detail.
3. Every selected cluster has expected `analytics_snapshots` generations.
4. Pages read the committed snapshot and do not create duplicate heavy queries.
5. Worker logs contain dataset, cluster, job execution ID, timeout, query count, retries, provider duration, source-lock wait, and failure code when applicable.
6. A failed refresh preserves the prior successful snapshot and displays remediation.

## Validation Performed

- Python compilation across application and tests.
- All Jinja templates parsed.
- Analytics and Job Configuration contract suites passed.
- Reliability-specific contracts verify no duplicate analytics health query, shared provider locking, retry behavior, horizon-aware deadlines, stale preservation, partial alert-source reporting, deterministic progress, and clear remediation.

The full Flask integration test suite could not be collected in the patch sandbox because Flask was not installed there. Runtime verification must still be performed in the KAORI development container after applying the patch.
