# Jobs & Executions

`app/jobs` is KAORI's canonical orchestration domain for background work. It owns job registration, scheduling policy, admission, `JobExecution` lifecycle, configuration UI, and worker/queue visibility. It does not own domain business logic.

## Canonical Flow

```text
Manual action / generic scheduler
→ registered JobDefinition
→ domain permission and scope resolution
→ canonical JobExecution create-or-attach
→ Celery queue
→ domain executor
→ progress, result, and terminal lifecycle
```

Every supported manual or scheduled operation must create or attach to a canonical `JobExecution`. Routes and scheduler code must never call a Celery domain task directly.

## Structure

- `registry.py` exposes the static job catalog.
- `definitions/` adapts registered jobs to their owning domains.
- `policies/` owns generic interval policy persistence and validation. Cron support requires an explicit scheduler extension before any definition may select it.
- `scheduler.py` claims due `JobPolicy` rows with database locks.
- `dispatcher.py` provides canonical dispatch and create-or-attach behavior.
- `routes.py` owns `/jobs/executions` and `/jobs/configuration`.
- `presentation.py` builds execution registry and queue views.
- `configuration.py` builds the job catalog and selected definition workspace.

## Ownership Boundary

The job domain may import a public domain dispatcher, but domain execution remains in its owner:

- Kubernetes inventory collection: `app.inventory` / `app.cluster`
- report generation: `app.reports`
- analytics materialization: `app.analytics`
- lifecycle archive: `app.retention`

Do not move collectors, report builders, analytics processors, or retention adapters into `app.jobs`.

## Registered Jobs

The first registered definition is `kubernetes.inventory.sync`:

- queue: `inventory`
- scope: `kubernetes_fleet:all`
- schedule: enabled by default every 60 minutes
- manual execution: supported
- domain execution permission: `clusters.sync`
- deduplication group: `kubernetes-inventory:global`

Additional jobs must be added through a new definition rather than a parallel scheduler or settings page.


Object Storage inventory is registered as `object_storage.inventory.sync`:

- queue: `inventory`
- scope: `object-storage-inventory:global`
- schedule: enabled by default every 60 minutes
- manual execution: supported
- domain execution permission: `storage.sync`
- manual authorization: `jobs.execute` + `storage.sync`
- deduplication group: `object-storage-inventory:global`

The Object Storage executor remains owned by `app.inventory.object_storage`. It resolves the provider through the integration registry and may pass a domain progress callback to `inventory.sync`; `app.jobs` owns orchestration and lifecycle only.

## RBAC

- `jobs.view`: view executions, queues, and configuration catalog.
- `jobs.execute`: manually dispatch registered jobs.
- `jobs.configure`: update automatic job policies.
- `jobs.cancel`: request cancellation for eligible executions.

A definition may require an additional domain permission. Inventory Sync requires both `jobs.execute` and `clusters.sync` for manual execution.

## Scheduler

Celery Beat runs `app.jobs.tasks.dispatch_scheduled_jobs` every minute on the maintenance queue. The task claims due `job_policies` rows with `FOR UPDATE SKIP LOCKED`, advances the next due time, and dispatches through the registry. Policy changes do not require a Beat restart.

## Analytics Definitions

The registry includes `analytics.materialize` and `analytics.forecast.materialize`. Both definitions use database-backed `JobPolicy`, canonical `JobExecution`, worker-specific queues, shared deduplication, and Activity Audit records for automatic runs. Scheduled jobs have no user subscriber and therefore do not produce notification-center items or toasts.

Analytics and Forecast policies are freshness-aware. A due policy check may complete with `current` and create no `JobExecution` when every configured snapshot is still reusable. This avoids periodic Prometheus queries that do not improve the data served to users.

### TLS Certificate Sync

`governance.tls_certificates.sync` refreshes Kubernetes TLS Secret certificate inventory through the
existing inventory worker. It defaults to a six-hour database-backed interval, supports manual execution,
and uses the same canonical deduplication and terminal audit behavior as other registered jobs. The owning
domain permission is `tls_certificates.sync`. User-facing execution, Notification Deck, cancellation, and automatic-audit labels resolve from the registered definition name, so the acronym remains **TLS Certificate Sync** rather than being reconstructed as `Tls Certificate Sync`.

## Job Progress Contract

All asynchronous job progress uses one canonical `JobExecution` progress contract and one shared UI renderer.
Domain workers keep `progress_current` / `progress_total` for completed work-item counts, while the reserved
`payload_json._progress` namespace carries a smooth 0–100 percentage plus the current stage and target.
This avoids overloading resource counts just to make a progress bar move.

Workers should report progress at meaningful boundaries only: stage transitions, resource-group boundaries,
or coarse percentage changes. High-cardinality collectors must not commit one `JobExecution` update per
individual object. Object Storage therefore reports bucket-level progress with percentage throttling, while
Kubernetes reports resource-family stages inside each cluster. Terminal success always normalizes progress
to 100%.

The shared `components/progress_bar.html::job_progress` renderer is the only progress presentation for
Jobs & Executions, Job Configuration, Activity Center, report execution details, and other JobExecution-backed
surfaces. Domain-specific progress toasts may wrap the same low-level violet bar primitive, but must not
introduce a second visual or percentage contract.
