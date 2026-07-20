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
