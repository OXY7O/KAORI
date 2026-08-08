# Platform Operations — Data Lifecycle

This package owns the KAORI **Data Lifecycle** operator workspace at `/platform-operations/data-lifecycle/`.

Ownership is intentionally split:

- `app/platform_operations/data_lifecycle/` owns HTTP routes, mutation orchestration, operator feedback, and workspace presentation.
- `app/retention/` remains the shared archive-first lifecycle engine, policy persistence layer, domain adapters, scheduling tasks, locking, verification, and cleanup safety boundary.
- `app/jobs/` remains the canonical execution ledger. Data Lifecycle may enqueue a canonical `JobExecution`, but it does not implement a second job registry.

The former `/settings/data-lifecycle/` route is compatibility-only and redirects to this workspace. Settings no longer owns lifecycle policy UI or mutation logic.

## Workspace contract

The page contains three controlled workspaces:

1. **Retention Policies** — per-domain retention, archive, schedule, and cleanup intent.
2. **Archive History** — verified archive artifacts and cleanup evidence. Canonical worker runtime remains under Jobs & Executions.
3. **Archive Storage** — shared target posture, verification evidence, worker dependency, and archive-first safety boundary.

Only registered archive adapters are displayed. Future domains are not advertised as placeholders before their adapter and safety contract exist.

## RBAC

- `platform_operations.view_data_lifecycle`
- `platform_operations.manage_data_lifecycle`
- `platform_operations.export_data_lifecycle`

The ownership-cutover migration renames the former `settings.*_data_lifecycle` permission rows in place, preserving role assignments and custom-role access.


## Execution semantics

Retention days define eligibility only. Automatic execution requires both the policy and its schedule to be enabled; Celery Beat checks due lifecycle policies every 15 minutes and dispatches due domains through the canonical `maintenance` execution path. Transient connectivity failures retry once automatically; exhausted or non-retryable failures keep cleanup blocked and require operator review/manual retry. A later scheduled window can dispatch a new run. Production already deploys a dedicated `maintenance-worker`, so a separate retention worker is unnecessary while `RETENTION_CELERY_QUEUE=maintenance`.
