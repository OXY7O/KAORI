# KAORI Data Lifecycle Foundation

This package provides the shared archive-first lifecycle used by **Platform Operations → Data Lifecycle**. The engine is domain-neutral: each source table supplies a small adapter, while policy persistence, archive writing, checksum verification, cleanup, scheduling, storage, canonical jobs, notifications, and execution history remain shared.

## Current managed domains

- `operational_activity`: canonical Activity Audit records plus persistent user Notification Center rows from the shared `notifications` table; transient toasts are excluded because they are not persisted.
- `job_execution`: terminal canonical worker executions and subscriber snapshots.
- `runtime_observation`: append-only Recent Runtime Observations for Kubernetes, Prometheus/Thanos, Alertmanager, and future providers using the shared `IntegrationRuntimeObservation` model.
- `analytics_snapshot`: reusable Analytics/Forecast materialization rows from `analytics_snapshots`; pending or still-serveable snapshots remain protected until stale grace and hot retention have both elapsed.

Future domains such as generated reports and Intelligence execution evidence should be added as adapters rather than separate retention subsystems.

## Safety invariants

1. Cleanup never starts until data and manifest artifacts are uploaded and independently verified by size and SHA-256 checksum.
2. Selection is frozen by cutoff and maximum source ID.
3. Cleanup receives the exact `source.record_id` values read back from the verified JSONL archive.
4. Lifecycle executions are canonical `JobExecution` records and deduplicate per data domain.
5. Archive object keys are immutable because they contain the archive UUID.
6. Registry rows preserve a non-secret storage locator snapshot after the active Local/S3 profile changes.
7. Cleanup is batched; partial completion is recorded as `cleanup_partial` and never removes the verified archive.
8. Active source records are protected by each domain adapter. The Job Execution adapter archives only terminal jobs and never follows `result_reference` into analytics, forecast, report, or dataset storage.

## Scale and scheduling

Celery Beat runs a lightweight dispatcher every 15 minutes. Persistent per-domain policies decide whether a domain is due and at what hour/minute. Due domains are fanned out as separate maintenance jobs, so Activity Audit, Job Execution, Runtime Observation, and Analytics Snapshot retention do not create one large database/storage burst.

Transient connectivity failures receive one bounded automatic retry using `RETENTION_RETRY_DELAY_SECONDS` (default 60 seconds). Non-retryable or exhausted failures remain terminal and keep cleanup blocked. Production consumes the default `RETENTION_CELERY_QUEUE=maintenance` through the existing dedicated `maintenance-worker`; only a custom retention queue requires an additional queue consumer.

The Data Lifecycle UI does not count every eligible record on ordinary page loads. Operators request an exact read-only preview only when needed. Source queries use indexed retention boundaries and bounded batches.

## Artifact format

- Data: compressed JSON Lines (`.jsonl.gz`) for streaming large datasets.
- Manifest: JSON with schema, selection boundary, record count, policy, storage locator, and checksum.
- Registry: `archive_artifacts` stores lifecycle status, object keys, counts, checksums, and execution metadata.

Every archived record contains:

```json
{
  "schema_version": 1,
  "domain": "domain_name",
  "source": {
    "model": "source_table_or_model",
    "record_id": 123
  }
}
```

## UI and CLI

The canonical UI is `/platform-operations/data-lifecycle/` with three workspaces:

- Retention Policies
- Archive History
- Archive Storage

No alternate Activity Audit retention route is registered; this workspace is the sole UI owner.

CLI and worker triggers still call the same service:

```bash
flask archive-retention preview --domain operational_activity
flask archive-retention run --domain operational_activity --archive-only
flask archive-retention run --domain job_execution --cleanup
flask archive-retention verify <archive-id>
flask archive-retention purge-archives --domain job_execution --execute
```

## Adding another domain

1. Implement the `ArchiveDomain` protocol in `app/retention/domains/`.
2. Register the adapter in `DOMAIN_FACTORIES`.
3. Define indexed eligibility boundaries and immutable serialization.
4. Explicitly define dependency and result-ownership rules; never rely on broad cascade deletion.
5. Add a seeded `DataLifecyclePolicy` and migration only when persistence defaults are required.
6. Add the domain to `ARCHIVE_SCHEDULED_DOMAINS` after scheduled execution is approved.
7. Add domain-specific tests for preview, serialization, verified cleanup, protected active data, and partial failure.

Restore/import remains an administrative capability and must include duplicate protection, schema compatibility validation, and explicit operator approval.

## Runtime observation lifecycle

`integration_runtime_observations` is an active `runtime_observation` lifecycle domain. Kubernetes, Prometheus/Thanos, and Alertmanager Recent Runtime Observations all persist into this provider-neutral model, so one lifecycle policy covers the three current integration families without provider-specific cleanup jobs. Runtime writes are append-only and no longer delete older rows through a per-connection rolling limit. Hot retention, archive verification, and cleanup are controlled centrally from **Platform Operations → Data Lifecycle**. The default policy keeps 90 days in PostgreSQL, retains verified archives for 365 days, and schedules the domain separately from Activity Audit and JobExecution.

## Operational activity lifecycle

`notifications` is the canonical persisted source for both the administrative **Activity Audit** and deck-visible **Notification Center** records. The `operational_activity` adapter archives every persisted row regardless of `deck_visible`, so audit-only events, user notifications, and authentication events remain under one archive-first policy. `protect_unreviewed` may extend hot retention for unread persisted records. Request-local transient toasts created without persistence are intentionally outside Data Lifecycle.

## Analytics snapshot lifecycle

`analytics_snapshots` is managed by the `analytics_snapshot` lifecycle adapter. The adapter archives Capacity, Utilization, Storage, Workload, Top Consumers, Alerts, dashboard materialization, and Forecast rows from the shared snapshot table. Cleanup never removes `pending` rows or snapshots that are still within their stale-serve window. Eligibility is frozen only after the stale deadline is older than the hot-retention cutoff; cleanup re-checks the current row before deletion so a concurrent refresh is preserved and produces `cleanup_partial` instead of deleting fresh evidence. The default hot-retention boundary is 30 days, verified archive retention is 180 days, and the scheduled window is 04:15 in the configured Celery timezone.
