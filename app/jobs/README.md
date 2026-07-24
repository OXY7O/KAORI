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

## RBAC

- `jobs.view`: view executions, queues, and configuration catalog.
- `jobs.execute`: manually dispatch registered jobs.
- `jobs.configure`: update automatic job policies.
- `jobs.cancel`: request cancellation for eligible executions.

A definition may require an additional domain permission. Inventory Sync requires both `jobs.execute` and `clusters.sync` for manual execution.

## Scheduler

Celery Beat runs `app.jobs.tasks.dispatch_scheduled_jobs` every minute on the maintenance queue. The dedicated `maintenance-worker` claims policies and dispatches jobs; Kubernetes inventory execution is consumed only by the dedicated `inventory-worker`. The task claims due `job_policies` rows with `FOR UPDATE SKIP LOCKED`, advances the next due time, and dispatches through the registry. Policy changes do not require a Beat restart.
