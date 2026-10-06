# KAORI Platform Operations — Data Lifecycle Final Lock v1.3

v1.3 supersedes v1.2 by admitting **Analytics Snapshots** as a managed archive-first lifecycle domain. Existing Activity Audit, Job Executions, Runtime Observations, Archive History, Archive Storage, and canonical Jobs & Executions boundaries remain unchanged.

## Managed domains

1. Activity Audit (`operational_activity`)
2. Analytics Snapshots (`analytics_snapshot`)
3. Job Executions (`job_execution`)
4. Runtime Observations (`runtime_observation`)

Only registered adapters may appear in the workspace.

## Analytics Snapshot boundary

- Source: `analytics_snapshots` / `AnalyticsSnapshot`.
- Coverage includes Analytics materialization, Forecast history, and shared dashboard materialization stored in the same table.
- `pending` snapshots are never archive-cleanup candidates.
- A snapshot with a payload remains protected until its freshness + stale-grace serve window has ended.
- Hot-retention time is applied after the stale-serve boundary, so retention never shortens the application serve window.
- Cleanup re-checks the current row before delete. A concurrently refreshed row must remain in hot storage; the archive may become `cleanup_partial` rather than deleting fresh evidence.
- Archive payload preserves dataset identity, parameters, materialized payload, status, generation/freshness metadata, and the canonical JobExecution reference.
- Default policy: 30 days hot, 180 days verified archive, 5000 batch, scheduled at 04:15 in the configured Celery timezone.
- Runtime uses the existing `maintenance` queue and canonical `JobExecution`; no analytics-specific retention worker is introduced.

## UI contract

The Retention Policies workspace exposes **Analytics Snapshots** with Lifecycle Coverage and a **Serve Window Protection** explanation. There are no placeholders for Reports or Intelligence until their own approved adapters and cleanup boundaries exist.
