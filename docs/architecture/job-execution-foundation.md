# KAORI Job Execution Foundation

## Purpose

The Job Execution Foundation is the canonical control plane for asynchronous work in KAORI. It prevents Flask requests from owning heavy provider operations and prepares Kubernetes Analytics, forecasting, reports, validation, and maintenance jobs to share one lifecycle contract.

```text
User / Scheduler
      ↓
Canonical JobExecution record in PostgreSQL
      ↓
Database deduplication + user/resource quota
      ↓
Celery queue selected by workload class
      ↓
Dedicated worker pool
      ↓
Progress heartbeat, result reference, toast, and Activity Audit
```

PostgreSQL is the source of truth for lifecycle state. Redis remains responsible for Celery broker traffic, fast distributed locks, resource slots, and short-lived polling metadata.

## Canonical models

All SQLAlchemy models remain centralized in `app/models/`:

```text
app/models/job.py
├── JobExecution
└── JobExecutionSubscriber
```

`JobExecution` records job type, operation, workload class, queue, priority, requester, provider/scope identity, deduplication key, parameter fingerprint, Celery task ID, progress, heartbeat, attempts, error, result reference, and lifecycle timestamps.

`JobExecutionSubscriber` records every user observing one shared execution. If two users request the same active validation or analytics job, KAORI dispatches one Celery task and subscribes both users to the same job.

## Multi-user deduplication

Active jobs populate `active_deduplication_key`, a nullable unique database column. Terminal jobs clear it.

```text
User A validates Prometheus 3
→ active key inserted
→ task dispatched

User B validates Prometheus 3 at the same time
→ unique active key already exists
→ User B is attached as subscriber
→ no duplicate provider query
```

The database constraint protects multiple Flask replicas and process races. PostgreSQL transaction advisory locks serialize per-user and per-resource admission checks, so distinct simultaneous submissions cannot bypass quotas. Redis locks remain an additional provider-resource guard for mutually exclusive integration operations.

## Job lifecycle

Canonical statuses:

```text
queued
running
retrying
cancel_requested
succeeded
partially_succeeded
failed
canceled
expired
```

Workers update `heartbeat_at` and progress. Beat runs `app.jobs.tasks.reconcile_stale_jobs` to expire running records with stale heartbeats, explicitly expired queued jobs, and orphan queued records that were never assigned a Celery task ID. A valid forecasting backlog is never expired merely because it waited in the queue. Redis restart therefore does not erase the operational history or active-job registry.

## Workload isolation

Queues and workers are separated by workload characteristics:

| Workload | Queue | Default concurrency | Purpose |
|---|---|---:|---|
| Inventory and maintenance | `inventory,maintenance` | 1 | inventory sync, retention, stale-job recovery |
| Runtime health | `integration-runtime` | 4 | short reachability and latency probes |
| Capability validation | `integration-validation` | 1 | provider discovery, RBAC, compatibility, binding evidence |
| Analytics batch | `analytics-batch` | 2 | capacity aggregation, anomaly preprocessing, materialization |
| Forecasting | `forecasting` | 1 | historical extraction, model execution, backtesting |

Forecasting and validation do not share a worker process. `max-tasks-per-child` is configured conservatively for heavy workers to limit long-lived memory growth.

## Quotas and fairness

Default guardrails:

```text
JOB_MAX_ACTIVE_PER_USER=5
JOB_MAX_HEAVY_PER_USER=1
JOB_MAX_ACTIVE_PER_RESOURCE=2
```

A user can still attach to an existing identical job even after reaching a quota because no additional work is created. New distinct work is rejected when the relevant user or resource budget is exhausted.

Future analytics jobs must use `app.jobs.dispatcher.enqueue_canonical_job()` rather than calling `apply_async()` directly. Admission is serialized by PostgreSQL advisory locks across all KAORI web replicas.

## Cancellation

Queued jobs are revoked and immediately marked canceled, releasing their active deduplication slot. Running validation/runtime jobs are not force-terminated because an interrupted provider request may leave incomplete evidence. Long-running analytics and forecasting tasks use `JobExecutionContext.checkpoint()` between chunks or model phases. A checkpoint refreshes the heartbeat and raises `JobCancellationRequested` when an operator requests cancellation.

Provider validation may not always be interruptible during one remote API call. The Job Execution UI therefore exposes cancellation only for queued work and active cooperative heavy workloads.

## Large query planning

Annual or long-range Prometheus/Thanos requests must use `app.jobs.query_planning`.

Default policy:

```text
maximum range               366 days
chunk size                   30 days
minimum step                  1 hour
maximum samples per series   10,000
concurrent queries/source     2
```

A one-year request is split into bounded chunks. The effective step is raised when required to stay under the sample budget. `app.jobs.query_execution` reserves a Redis-backed per-source query slot and provides a mandatory heartbeat/cancellation checkpoint for every chunk. Workers should persist intermediate datasets or object-storage references and update progress after each chunk.

```text
Historical source
→ 30-day bounded queries
→ hourly/downsampled analytical dataset
→ local model execution
→ persisted forecast result
→ UI reads result, not raw one-year query
```

## Result storage

Small summaries may be stored in `result_summary_json`. Large outputs must use `result_reference` to point to a durable artifact such as PostgreSQL summary tables or S3-compatible Parquet/object storage. Redis and Celery results are not durable analytics result stores.

## Operational visibility

`Integrations → Review Jobs` opens the Job Execution Registry. It provides status, queue, scope, requester, progress, duration, filters, and safe cancellation controls. Pagination follows the KAORI default of 5 with 5/10/25/50 choices.

## Implementation boundaries

```text
app/jobs/
├── dispatcher.py        # canonical create/deduplicate/dispatch entry point
├── execution.py         # cooperative worker lifecycle helper
├── fingerprint.py       # deterministic parameter fingerprints
├── query_planning.py    # large-range chunk and sample guardrails
├── query_execution.py   # per-source slots and chunk checkpoints
├── resource_limits.py   # Redis-backed per-source execution slots
├── service.py           # PostgreSQL lifecycle, quota, subscriber, recovery
└── tasks.py             # maintenance/recovery tasks
```

Provider code owns provider-specific queries. The Job Execution Foundation owns lifecycle, dispatch, deduplication, quotas, progress, cancellation, and recovery.


## Celery priority contract

KAORI uses Redis-compatible Celery priorities from 0 through 9. Lower values are processed first: runtime `2`, validation `3`, standard `5`, analytics `6`, and forecasting `7`. Queue isolation remains the primary protection; priority only orders work inside one queue.
