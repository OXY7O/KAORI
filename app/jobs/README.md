# KAORI Job Execution Foundation

## Purpose

`app/jobs` provides the canonical execution lifecycle for validation, runtime, analytics, forecasting, maintenance, and other background workloads. PostgreSQL is the source of truth for job state. Redis remains the broker, distributed-lock service, resource-slot coordinator, and transient progress channel.

## Multi-user contract

Identical active requests attach to one `JobExecution` through the active deduplication key. Each requesting user is recorded as a `JobExecutionSubscriber`; KAORI must not enqueue duplicate work merely because several users click the same action.

## Job records and Activity Audit records are different

`JobExecution` records are operational execution state. They contain queue ownership, progress, attempts, worker state, result references, and cancellation state.

Activity Audit records answer who requested, changed, canceled, completed, or failed an operation. They are an immutable administrative trail and must remain independently reviewable after the hot job row is removed.

For that reason, Job Execution records must never be cleaned by deleting matching Activity Audit records, and Activity Audit retention must not be treated as Job Registry retention.

## Retention direction

KAORI should use the existing archive-first retention engine with a separate `job_execution` domain. It may be presented inside the same **Retention & Archive** workspace as Operational Activity, but each domain needs its own policy, preview, archive manifest, cleanup boundary, and execution history.

Recommended initial policy:

- active jobs: never eligible;
- terminal runtime and validation jobs: retain in PostgreSQL for 30 days;
- terminal analytics and forecasting jobs: retain for 90 days or until their result reference expires, whichever is later;
- failed jobs: retain for at least 90 days;
- archive artifacts: retain for 365 days;
- result artifacts and datasets: governed by their owning analytics/report/storage policy, not by deleting the JobExecution row;
- subscribers: archived with the job and removed through the JobExecution cascade only after archive verification.

Until the `job_execution` archive domain and its UI are implemented, deployments should monitor `job_executions` growth and must not enable ad-hoc database deletion scripts.

## Registry refresh contract

The Job Execution Registry provides an explicit HTMX `Refresh` action in its block header. Refresh preserves the active page, page size, and filters, swaps only `#job-execution-registry`, and uses the standard loading bar directly below the title header. The action does not reload the full Jobs & Executions page.

## Navigation and Workspace Contract

Jobs & Executions is a cross-domain KAORI operational workspace. It is presented under **Platform Operations**, not inside the Integrations submenu, because the registry covers validation, runtime, analytics, forecasting, reporting, lifecycle, and future background workloads.

The `/integrations/jobs` URL is retained as a compatibility path for existing bookmarks, notifications, and audit action links. Information architecture is controlled by sidebar placement rather than forcing a breaking URL migration.

The workspace has three views:

- **Active Work** for live progress and cancellation boundaries.
- **Execution Registry** for searchable historical execution records.
- **Queue Activity** for database-backed workload demand by queue. Queue Activity does not claim worker process liveness.

The overview must distinguish canonical job state from actual worker health. Worker liveness belongs to deployment monitoring or Celery inspection, while this workspace remains the source of truth for execution lifecycle, ownership, progress, and results.

## Progress and cancellation contract

Active Work uses a determinate bar only when the worker publishes `progress_current` and `progress_total`. A running job without a trustworthy total uses an indeterminate animation and the label `In Progress`; KAORI must not display a decorative `0%` as if it were measured progress. Integration validation and runtime workers publish phase-level progress while analytics and forecasting workers publish chunk/model-phase progress.

Queued jobs can be canceled before provider execution. Running analytics and forecasting jobs use cooperative checkpoints. Running validation and runtime provider calls are shown as **Protected Run** because KAORI does not force-terminate a network/API request mid-flight; this boundary is provider-neutral and applies equally to Kubernetes, Prometheus, and Alertmanager.

## RBAC contract

Jobs & Executions uses dedicated cross-domain permissions:

- `jobs.view` opens Platform Operations and the execution workspace.
- `jobs.cancel` requests cancellation for eligible jobs and depends on `jobs.view`.

The jobs workspace must not reuse `settings.manage_integrations`. The migration preserves existing access for custom roles that previously reached the page through integration, Data Lifecycle, or Activity Audit permissions, after which administrators can review the narrower contracts in Roles & Access.
