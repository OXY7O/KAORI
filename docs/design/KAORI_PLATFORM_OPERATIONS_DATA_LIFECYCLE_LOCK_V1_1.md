# KAORI Platform Operations — Data Lifecycle Final Lock v1.1

Status: Final Lock
Date: 2026-08-08
Owner: Platform Operations

## Purpose

v1.1 refines the locked Data Lifecycle workspace after operational review. Ownership remains unchanged: Platform Operations owns lifecycle policy and archive evidence, `app/retention/` owns the archive-first engine, and Jobs & Executions owns canonical asynchronous runtime evidence.

## Workspace Order

The canonical tab order is:

```text
Retention Policies → Archive History → Archive Storage
```

The order follows normal operator frequency: define intent, inspect evidence/results, then inspect the shared infrastructure contract. Archive Storage is a shared platform dependency rather than a per-domain workflow step.

## Retention Execution Semantics

1. Changing `Hot retention days` changes the eligibility boundary only. It does **not** immediately create a job.
2. Automatic execution requires both `Policy enabled` and `Scheduled execution`.
3. Celery Beat publishes the Data Lifecycle dispatcher every 15 minutes. The dispatcher evaluates each domain's configured daily hour/minute and dispatches a canonical `data_lifecycle` JobExecution only when due.
4. Transient connectivity failures receive one bounded automatic retry after `RETENTION_RETRY_DELAY_SECONDS` (default 60 seconds). Cleanup remains fail-closed during retry.
5. Exhausted or non-retryable failures become terminal and require operator review/manual retry; a future due schedule may dispatch a new run.
6. Worker loss is protected by Celery `acks_late` and `reject_on_worker_lost`; this is separate from application-level retry semantics.
7. Production uses the dedicated `maintenance-worker` service. Retention defaults to the `maintenance` queue; a custom `RETENTION_CELERY_QUEUE` requires a worker that consumes that queue.
8. Generic retry/cancellation/runtime evidence remains owned by Jobs & Executions.

## Presentation Contract

- Managed-domain helper copy is compact: `Only approved lifecycle domains are manageable.`
- Job Execution domain copy is compact: `Canonical queue, progress, results, and worker metadata.`
- Retention Policies exposes `Retention Boundary`, `Automatic Run`, `Failure Recovery`, and `Execution Worker` evidence next to schedule controls.
- Data Lifecycle uses `components/loading_bar.html` for HTMX loading bars. Page-local `notification-progress-indeterminate` bars are forbidden.
- Archive History uses the canonical pagination footer macros. `Rows` is `text-xs`, matching the summary and page-size control.

## Archive Storage Contract

Archive Storage is an operational evidence workspace, not a decorative configuration summary. It must show:

- Storage Readiness;
- Worker Readiness and worker count;
- Last Verified archive evidence;
- Archive Format;
- Archive Target Contract (provider, location, endpoint/bucket where relevant, queue);
- Execution Contract (dispatcher, scheduling prerequisite, failure recovery, worker isolation);
- Archive-First Safety Boundary (`Freeze Boundary → Write Archive → Verify Evidence → Cleanup Hot Data`);
- Storage Interpretation, explicitly distinguishing endpoint reachability from verified write/read/checksum evidence.

Storage credentials remain deployment-managed and must not be rendered.

## Sidebar Dark-Mode Refinement

The active parent menu remains a controlled Violet surface, but dark mode must not draw a separate inset Violet line on the left edge. Active state remains clear through surface, border, icon, and typography.

## Enforcement

```bash
python scripts/verify_data_lifecycle_final_lock.py
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_sidebar_navigation_standard.py
python scripts/verify_dark_mode_standard.py
pytest -q tests/contracts/platform_operations
```
