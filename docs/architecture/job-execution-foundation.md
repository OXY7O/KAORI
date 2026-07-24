# KAORI Job Execution Foundation

## Purpose

The Job Execution Foundation is the canonical control plane for asynchronous work in KAORI. It prevents Flask requests from owning heavy provider operations and prepares Kubernetes Analytics, forecasting, reports, validation, and maintenance jobs to share one lifecycle contract.

```text
Manual action / generic policy scheduler
      ↓
Registered JobDefinition and domain permission resolution
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
├── JobExecutionSubscriber
└── JobPolicy
```

`JobExecution` records job type, operation, workload class, queue, priority, requester, provider/scope identity, deduplication key, parameter fingerprint, Celery task ID, progress, heartbeat, attempts, error, result reference, and lifecycle timestamps.

`JobExecutionSubscriber` records every user observing one shared execution. If two users request the same active validation or analytics job, KAORI dispatches one Celery task and subscribes both users to the same job.

`JobPolicy` stores the database-backed automatic execution policy for one registered job and scope. The first policy is `kubernetes.inventory.sync` for the all-cluster Kubernetes inventory fleet. Policy edits do not restart Celery Beat.

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
| Kubernetes inventory | `inventory` | 1 | fleet and single-cluster inventory synchronization |
| Job maintenance | `maintenance` | 1 | policy dispatch, retention, and stale-job recovery |
| Runtime health | `integration-runtime` | 4 | short reachability and latency probes |
| Capability validation | `integration-validation` | 1 | provider discovery, RBAC, compatibility, binding evidence |
| Analytics batch | `analytics-batch` | reserved | capacity aggregation, anomaly preprocessing, materialization |
| Forecasting | `forecasting` | reserved | historical extraction, model execution, backtesting |

Inventory and maintenance are intentionally isolated because inventory collection is provider-heavy while policy dispatch and recovery must remain responsive. The analytics and forecasting queue names are reserved application contracts, but production worker services are intentionally not deployed until concrete task modules and routes exist. When those tasks are introduced, they must use dedicated workers; forecasting and validation must never share a worker process.

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

Large-range Prometheus or Thanos execution is intentionally not preimplemented. The first Analytics worker that requires historical chunking must introduce its query-plan contract, provider concurrency guard, persistence model, and functional tests in the same domain change. KAORI must not carry dormant worker infrastructure that is not invoked by a production task.

The required execution shape remains:

```text
Historical source
→ bounded provider queries
→ downsampled analytical dataset
→ local model execution
→ persisted result
→ UI reads the persisted result
```

## Result storage

Small summaries may be stored in `result_summary_json`. Large outputs must use `result_reference` to point to a durable artifact such as PostgreSQL summary tables or S3-compatible Parquet/object storage. Redis and Celery results are not durable analytics result stores.

## Operational visibility

`Platform Operations → Jobs & Executions` owns two top-level workspaces:

- **Executions** provides active work, the server-paginated registry, queue demand, progress, requester, timing, result, and safe cancellation controls.
- **Job Configuration** provides the registered job catalog, automatic policy controls, manual execution, recent execution history, and domain safety boundaries.

Inventory Sync is the first registered configuration. Future report, analytics, forecasting, retention, and reconciliation jobs must register here rather than introducing a new Settings page or parallel scheduler.

## Implementation boundaries

```text
app/jobs/
├── routes.py            # Executions and Job Configuration workspaces
├── registry.py          # static registered-job catalog
├── configuration.py     # generic catalog and selected-job presentation
├── definitions/         # metadata-only adapters to owning domains
├── policies/            # generic policy form, persistence, and presentation
├── scheduler.py         # database claim and registered dispatch
├── dispatcher.py        # canonical create/deduplicate/dispatch entry point
├── execution.py         # cooperative worker lifecycle helper
├── fingerprint.py       # deterministic parameter fingerprints
├── service.py           # PostgreSQL lifecycle, quota, subscriber, recovery
└── tasks.py             # policy dispatch and maintenance/recovery tasks
```

Provider and feature domains own their collectors, report builders, analytics processors, and retention adapters. `app.jobs` owns registration, policy, lifecycle, dispatch, deduplication, quotas, progress, cancellation, and recovery. Definitions may resolve a domain adapter dynamically, but business logic must not move into the jobs package.


## Celery priority contract

KAORI uses Redis-compatible Celery priorities from 0 through 9. Lower values are processed first: runtime `2`, validation `3`, standard `5`, analytics `6`, and forecasting `7`. Queue isolation remains the primary protection; priority only orders work inside one queue.
