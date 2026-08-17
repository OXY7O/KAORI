# Platform Operations — Data Lifecycle

This package owns the KAORI **Data Lifecycle** operator workspace at `/platform-operations/data-lifecycle/`.

Ownership is intentionally split:

- `app/platform_operations/data_lifecycle/` owns HTTP routes, mutation orchestration, operator feedback, and workspace presentation.
- `app/platform_operations/data_lifecycle/retention/` remains the shared archive-first lifecycle engine, policy persistence layer, domain adapters, scheduling tasks, locking, verification, and cleanup safety boundary.
- `app/platform_operations/jobs/` remains the canonical execution ledger. Data Lifecycle may enqueue a canonical `JobExecution`, but it does not implement a second job registry.

The former `/settings/data-lifecycle/` route is compatibility-only and redirects to this workspace. Settings no longer owns lifecycle policy UI or mutation logic.

## Workspace contract

The page contains three controlled, server-owned workspaces. Only the active workspace is built on a request, so Archive History queries and Archive Storage probes do not run while an operator is editing Retention Policies:

1. **Retention Policies** — per-domain retention, archive, schedule, and cleanup intent.
2. **Archive History** — verified archive artifacts and cleanup evidence. Canonical worker runtime remains under Jobs & Executions.
3. **Archive Storage** — shared target posture, verification evidence, worker dependency, and archive-first safety boundary.

Only registered archive adapters are displayed. Retention Policies remain preview-first and manual execution is fail-closed when the persisted policy is missing, while a policy is paused, or while another lifecycle execution for that domain is active. Archive History preserves filters, pagination, and Rows context when an operator re-verifies evidence. Archive Storage reports the newest verified evidence that matches the currently configured storage profile across all managed domains, rather than inheriting the selected policy domain. Future domains are not advertised as placeholders before their adapter and safety contract exist. The policy workspace also exposes **Lifecycle Coverage** so operators can see which product surfaces share each source model: Activity Audit and persistent Notification Center rows share `operational_activity`, while Kubernetes, MinIO Object Storage, Metrics Source, and Alertmanager Recent Runtime Observations share `runtime_observation`. Reusable Analytics and Forecast materializations are governed by the `analytics_snapshot` adapter with explicit stale-serve protection. Generated report metadata and retained PDF/XLSX/CSV artifacts are governed by the `generated_report` adapter with active-generation protection and binary checksum verification. The Generated Reports policy is seeded paused and must be explicitly enabled after archive-storage readiness and Preview are reviewed.

## RBAC

- `platform_operations.view_data_lifecycle`
- `platform_operations.manage_data_lifecycle`
- `platform_operations.export_data_lifecycle`

The ownership-cutover migration renames the former `settings.*_data_lifecycle` permission rows in place, preserving role assignments and custom-role access.


## Execution semantics

Retention days define eligibility only. Automatic execution requires an enabled persisted policy, its schedule to be enabled, and the global `DATA_LIFECYCLE_SCHEDULER_ENABLED` dispatcher gate to be on. Celery Beat checks due lifecycle policies every 15 minutes and dispatches due domains through the canonical `maintenance` execution path. The UI exposes the dispatcher gate explicitly and suppresses a misleading next-run timestamp while it is disabled. Transient connectivity failures retry once automatically; exhausted or non-retryable failures keep cleanup blocked and require operator review/manual retry. A later scheduled window can dispatch a new run. Production already deploys a dedicated `maintenance-worker`, so a separate retention worker is unnecessary while `RETENTION_CELERY_QUEUE=maintenance`.


## Archive purge safety

Expired cold archives are purged in a bounded batch (`ARCHIVE_PURGE_BATCH_SIZE`, default 250). If object deletion only partially succeeds, the registry row becomes `purge_failed`; the UI no longer advertises the archive as downloadable, the canonical lifecycle JobExecution is marked partially succeeded, and a later lifecycle run may retry the idempotent deletion.

### Storage ownership

Lifecycle domains do not configure independent archive buckets. Hot source storage remains domain-owned (for example, Runtime Observations live in PostgreSQL table `integration_runtime_observations`), while every domain writes verified cold evidence to the shared **Archive Storage** profile. Runtime Observations archive structured provider-neutral evidence as JSONL.GZ + manifest JSON and do not carry supplemental binary artifacts. Generated Reports are the exception at the payload level: their PDF/XLSX/CSV files are copied as supplemental evidence into the same shared archive target. The Retention Policies workspace exposes this boundary without probing the backend; readiness and verification stay demand-loaded in **Archive Storage**.
