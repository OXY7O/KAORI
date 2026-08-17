# KAORI Data Lifecycle Foundation

This package provides the shared archive-first lifecycle used by **Platform Operations → Data Lifecycle**. The engine is domain-neutral: each source table supplies a small adapter, while policy persistence, archive writing, checksum verification, cleanup, scheduling, storage, canonical jobs, notifications, and execution history remain shared.

## Current managed domains

- `operational_activity`: canonical Activity Audit records plus persistent user Notification Center rows from the shared `notifications` table; transient toasts are excluded because they are not persisted.
- `job_execution`: terminal canonical worker executions and subscriber snapshots.
- `runtime_observation`: append-only Recent Runtime Observations for Kubernetes, MinIO Object Storage, Prometheus/Thanos, Alertmanager, and future providers using the shared `IntegrationRuntimeObservation` model.
- `analytics_snapshot`: reusable Analytics/Forecast materialization rows from `analytics_snapshots`; pending or still-serveable snapshots remain protected until stale grace and hot retention have both elapsed.
- `generated_report`: terminal Generated Reports metadata from `reports`; Ready and Archived rows archive their binary PDF/XLSX/CSV evidence with SHA-256 verification before source cleanup, while active generation remains protected.

Future domains such as Intelligence execution evidence should be added as adapters rather than separate retention subsystems.

## Safety invariants

1. Cleanup never starts until data and manifest artifacts are uploaded and independently verified by size and SHA-256 checksum.
2. Selection is frozen by one selection timestamp, cutoff, and maximum source ID.
3. Cleanup receives the exact `source.record_id` values read back from the verified JSONL archive.
4. Lifecycle executions are canonical `JobExecution` records and deduplicate per data domain.
5. Archive object keys are immutable because they contain the archive UUID.
6. Registry rows preserve a non-secret storage locator snapshot after the active Local/S3 profile changes.
7. Cleanup is batched; partial completion is recorded as `cleanup_partial` and never removes the verified archive.
8. Active source records are protected by each domain adapter. The Job Execution adapter archives only terminal jobs and never follows `result_reference` into analytics, forecast, report, or dataset storage.

## Scale and scheduling

Celery Beat runs one lightweight Data Lifecycle dispatcher every 15 minutes while `DATA_LIFECYCLE_SCHEDULER_ENABLED=true`. Persistent per-domain policy rows are authoritative for whether a domain is due and at what hour/minute; legacy per-domain environment defaults no longer decide whether the dispatcher itself exists. The operator workspace surfaces the global dispatcher state so a saved schedule is never presented as having a next automatic run while dispatch is globally disabled. Due domains are fanned out as separate maintenance jobs, so Activity Audit, Job Execution, Runtime Observation, Analytics Snapshot, and Generated Report retention do not create one large database/storage burst.

Transient connectivity failures receive one bounded automatic retry using `RETENTION_RETRY_DELAY_SECONDS` (default 60 seconds). Non-retryable or exhausted failures remain terminal and keep cleanup blocked. Production consumes the default `RETENTION_CELERY_QUEUE=maintenance` through the existing dedicated `maintenance-worker`; only a custom retention queue requires an additional queue consumer.

The Data Lifecycle UI does not count every eligible record on ordinary page loads. Operators request an exact read-only preview only when needed. Retention Policies, Archive History, and Archive Storage are server-owned demand-loaded workspaces, so history pagination, storage endpoint probing, and worker readiness are not all evaluated on every page request. Ordinary GET requests never create lifecycle policy rows. A missing persisted policy is fail-closed: it is shown disabled and cannot queue manual or scheduled archive execution until an operator saves an authoritative policy. Source queries use indexed retention boundaries and bounded batches.

Archive selection stores one `selected_at` timestamp and reuses that exact time, cutoff, and maximum source ID while metadata, JSONL data, and supplemental evidence are written. This prevents rows from entering the archive merely because they crossed an age threshold while a long-running archive was already in progress. Expired archive deletion is separately bounded by `ARCHIVE_PURGE_BATCH_SIZE` (default 250, maximum 2,500). A partial purge is marked `purge_failed`, is no longer downloadable as a complete archive, and remains eligible for a later idempotent purge retry.

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

`integration_runtime_observations` is an active `runtime_observation` lifecycle domain. Kubernetes, MinIO Object Storage, Prometheus/Thanos, and Alertmanager Recent Runtime Observations all persist into this provider-neutral model, so one lifecycle policy covers the current integration families without provider-specific cleanup jobs. Runtime writes are append-only and no longer delete older rows through a per-connection rolling limit. Hot retention, archive verification, and cleanup are controlled centrally from **Platform Operations → Data Lifecycle**. The default policy keeps 90 days in PostgreSQL, retains verified archives for 365 days, and schedules the domain separately from Activity Audit and JobExecution.

## Operational activity lifecycle

`notifications` is the canonical persisted source for both the administrative **Activity Audit** and deck-visible **Notification Center** records. The `operational_activity` adapter archives every persisted row regardless of `deck_visible`, so audit-only events, user notifications, and authentication events remain under one archive-first policy. `protect_unreviewed` may extend hot retention for unread persisted records. Request-local transient toasts created without persistence are intentionally outside Data Lifecycle.

## Analytics snapshot lifecycle

`analytics_snapshots` is managed by the `analytics_snapshot` lifecycle adapter. The adapter archives Capacity, Utilization, Storage, Workload, Top Consumers, Alerts, dashboard materialization, and Forecast rows from the shared snapshot table. Cleanup never removes `pending` rows or snapshots that are still within their stale-serve window. Eligibility is frozen only after the stale deadline is older than the hot-retention cutoff; cleanup re-checks the current row before deletion so a concurrent refresh is preserved and produces `cleanup_partial` instead of deleting fresh evidence. The default hot-retention boundary is 30 days, verified archive retention is 180 days, and the scheduled window is 04:15 in the configured Celery timezone.

## Generated report lifecycle

`reports` is managed by the `generated_report` lifecycle adapter. The policy is seeded **paused by default** so a deployment upgrade never starts deleting historical report evidence automatically. After an operator reviews archive storage, runs Preview, and explicitly enables the policy/schedule, the recommended baseline keeps Ready reports in the hot Generated registry for 90 days, Failed reports for 30 days, and manually Archived reports for 180 days. Verified lifecycle archives are retained for 365 days and run in bounded batches of 250 because a batch may transfer report binaries in addition to JSON metadata. The generated-report adapter hard-limits a batch to 2,500 records even if a larger shared lifecycle value is submitted. Requested, Queued, Generating, and reports attached to an active generation job are excluded. Ready and Archived rows must have a retained artifact reference; the lifecycle engine copies each PDF, XLSX, or CSV into the archive namespace and independently verifies its size and SHA-256 checksum before source artifact deletion or database cleanup can begin.

The Generated Reports table remains a hot operational registry. Data Lifecycle owns age/status-based archive and cleanup; row count is never used as the deletion trigger. Reports Storage only mirrors the policy and provides storage-level candidate diagnostics.

### Storage ownership

Lifecycle domains do not configure independent archive buckets. Hot source storage remains domain-owned (for example, Runtime Observations live in PostgreSQL table `integration_runtime_observations`), while every domain writes verified cold evidence to the shared **Archive Storage** profile. Runtime Observations archive structured provider-neutral evidence as JSONL.GZ + manifest JSON and do not carry supplemental binary artifacts. Generated Reports are the exception at the payload level: their PDF/XLSX/CSV files are copied as supplemental evidence into the same shared archive target. The Retention Policies workspace exposes this boundary without probing the backend; readiness and verification stay demand-loaded in **Archive Storage**.
