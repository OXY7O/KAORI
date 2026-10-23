# KAORI Data Lifecycle Foundation

This package provides the shared archive-first lifecycle used by **Platform Operations → Data Lifecycle**. The engine is domain-neutral: each source table supplies a small adapter, while policy persistence, archive writing, checksum verification, cleanup, scheduling, storage, canonical jobs, notifications, and execution history remain shared.

## Current managed domains

- `operational_activity`: canonical Activity Audit records plus persistent user Notification Center rows from the shared `notifications` table; transient toasts are excluded because they are not persisted.
- `job_execution`: terminal canonical worker executions and subscriber snapshots.
- `runtime_observation`: append-only Recent Runtime Observations for Kubernetes, MinIO Object Storage, Metrics Source, Alertmanager, and future providers using the shared `IntegrationRuntimeObservation` model.
- `analytics_snapshot`: reusable Analytics/Forecast materialization rows from `analytics_snapshots`; pending or still-serveable snapshots remain protected until stale grace and hot retention have both elapsed.
- `generated_report`: terminal Generated Reports metadata from `reports`; Ready and Archived rows archive their binary PDF/XLSX/CSV evidence with SHA-256 verification before source cleanup, while active generation remains protected.
- `alert_incident`: closed Alert Operations case evidence (timeline, notification delivery, postmortem) with compacted hot case index preserved for History.
- `tenant_audit_evidence`: committed normalized Tenant/Kubernetes audit correlation evidence; the Kubernetes API audit provider remains authoritative for raw event logs.
- `audit_event`: separate source-owned administrative `audit_events` across KAORI producers; paused manual archive-only, summary/redaction only. Raw metadata and archive export are not admitted.

The registered adapter catalog now contains **nine** managed domains after paused, archive-only Notification Delivery and AuditEvent extensions (historical seven-domain catalog before #2848). The Data Lifecycle Final Lock v1.3 documents the four-domain historical admission baseline; later registered adapters follow the same approved archive-first engine and do not rewrite that historical lock. Adapter registration alone does not enable unattended execution: persisted policy and scheduler domain configuration still govern automation.

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

## Re-verification and recovery of archive evidence

Archive History **Verify** re-reads the data, manifest and any supplementary artifacts from the original storage locator and compares size and SHA-256 evidence. If any object is missing, inaccessible or mismatched, the archive moves to `failed`, its previous verification timestamp is invalidated, and Data/Manifest download is blocked until a successful re-verification. Re-verification is an integrity check, not a hot-data restore or a cleanup retry.

On successful re-verification of a previously failed archive, `archive_and_cleanup` records with `cleanup_deleted_count < record_count` remain `cleanup_partial` even if zero source rows were deleted. The operator must review the original failed execution and remaining hot records before starting a separate governed lifecycle run. Archive-only or fully completed cleanup may return to `ready` after integrity checks pass. `purge_failed`/`expired` artifacts cannot be silently reset by the Verify action; their own purge/recovery contract remains authoritative.

## Atomic policy mutation

Saving a previously absent lifecycle policy stages the fallback row and submitted operator values in **one database transaction**. It never commits default enablement or schedule values before the requested policy state is committed. A failed save rolls back the whole first-save operation; ordinary GET/Preview requests do not create policy rows. Existing seeded policies continue to be updated through the same authoritative persisted-policy service.

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

1. Implement the `ArchiveDomain` protocol in `app/platform_operations/data_lifecycle/retention/domains/`.
2. Register the adapter in `DOMAIN_FACTORIES`.
3. Define indexed eligibility boundaries and immutable serialization.
4. Explicitly define dependency and result-ownership rules; never rely on broad cascade deletion.
5. Add a seeded `DataLifecyclePolicy` and migration only when persistence defaults are required.
6. Add the domain to `ARCHIVE_SCHEDULED_DOMAINS` after scheduled execution is approved.
7. Add domain-specific tests for preview, serialization, verified cleanup, protected active data, and partial failure.

Restore/import remains an administrative capability and must include duplicate protection, schema compatibility validation, and explicit operator approval.

## Runtime observation lifecycle

`integration_runtime_observations` is an active `runtime_observation` lifecycle domain. Kubernetes, MinIO Object Storage, Metrics Source, and Alertmanager Recent Runtime Observations all persist into this provider-neutral model, so one lifecycle policy covers the current integration families without provider-specific cleanup jobs. Runtime writes are append-only and no longer delete older rows through a per-connection rolling limit. Hot retention, archive verification, and cleanup are controlled centrally from **Platform Operations → Data Lifecycle**. The default policy keeps 90 days in PostgreSQL, retains verified archives for 365 days, and schedules the domain separately from Activity Audit and JobExecution.

## Operational activity lifecycle

`notifications` is the canonical persisted source for both the administrative **Activity Audit** and deck-visible **Notification Center** records. The `operational_activity` adapter archives every persisted row regardless of `deck_visible`, so audit-only events, user notifications, and authentication events remain under one archive-first policy. Archive schema v2 copies the immutable `actor_snapshot_json` committed with the notification row and never reconstructs actor identity from the live User table. `protect_unreviewed` may extend hot retention for unread persisted records. Request-local transient toasts created without persistence are intentionally outside Data Lifecycle.

## Analytics snapshot lifecycle

`analytics_snapshots` is managed by the `analytics_snapshot` lifecycle adapter. The adapter archives Capacity, Utilization, Storage, Workload, Top Consumers, Alerts, dashboard materialization, and Forecast rows from the shared snapshot table. Cleanup never removes `pending` rows or snapshots that are still within their stale-serve window. Eligibility is frozen only after the stale deadline is older than the hot-retention cutoff; cleanup re-checks the current row before deletion so a concurrent refresh is preserved and produces `cleanup_partial` instead of deleting fresh evidence. The default hot-retention boundary is 30 days, verified archive retention is 180 days, and the scheduled window is 04:15 in the configured Celery timezone.

## Generated report lifecycle

`reports` is managed by the `generated_report` lifecycle adapter. The policy is seeded **paused by default** so a deployment upgrade never starts deleting historical report evidence automatically. After an operator reviews archive storage, runs Preview, and explicitly enables the policy/schedule, the recommended baseline keeps Ready reports in the hot Generated registry for 90 days, Failed reports for 30 days, and manually Archived reports for 180 days. Verified lifecycle archives are retained for 365 days and run in bounded batches of 250 because a batch may transfer report binaries in addition to JSON metadata. The generated-report adapter hard-limits a batch to 2,500 records even if a larger shared lifecycle value is submitted. Requested, Queued, Generating, and reports attached to an active generation job are excluded. Ready and Archived rows must have a retained artifact reference; the lifecycle engine copies each PDF, XLSX, or CSV into the archive namespace and independently verifies its size and SHA-256 checksum before source artifact deletion or database cleanup can begin.

The Generated Reports table remains a hot operational registry. Data Lifecycle owns age/status-based archive and cleanup; row count is never used as the deletion trigger. Reports Storage only mirrors the policy and provides storage-level candidate diagnostics.

### Storage ownership

Lifecycle domains do not configure independent archive buckets. Hot source storage remains domain-owned (for example, Runtime Observations live in PostgreSQL table `integration_runtime_observations`), while every domain writes verified cold evidence to the shared **Archive Storage** profile. Runtime Observations archive structured provider-neutral evidence as JSONL.GZ + manifest JSON and do not carry supplemental binary artifacts. Generated Reports are the exception at the payload level: their PDF/XLSX/CSV files are copied as supplemental evidence into the same shared archive target. The Retention Policies workspace exposes this boundary without probing the backend; readiness and verification stay demand-loaded in **Archive Storage**.

## Notification Delivery ledger schema-only extension (#2868)

A candidate durable identity schema can reserve `(channel_id,event_key)`
without copying secrets or transport replay data. The model/migration is
**inert by default**: no writer, backfill, dispatch behavior, archive lookup
or cleanup enablement is introduced. The hot `NotificationDelivery` unique
key is still authoritative. Apply the versioned migration only in the
approved DevContainer migrator context, then validate schema and PostgreSQL
behavior before designing an atomic dual-write rollout. See
`docs/architecture/notification-delivery-lifecycle-safety.md`.

## Notification Delivery — archive-only safety admission (#2848)

`notification_delivery` is a separate provider-neutral archive domain for
`notification_deliveries`; it is **not** the persistent user Notification Center
(`operational_activity`) and **not** a substitute for Activity Audit or Alert
Incident archives. It uses the shared preview, immutable JSONL.GZ and manifest,
verified storage, canonical Jobs, policy and permission controls.

First admission is **paused, manual, archive-only** (90-day eligible hot boundary,
365-day archive-retention proposal, batch size 1,000). Only aged `sent` and
`skipped` records with both `created_at` and `updated_at` older than the cutoff
are selected. `queued` and all `failed` attempts are protected while recovery
rules remain provider/domain-owned. Archives retain event/channel correlation,
status, attempts and timestamp fields, but **not** `payload_json`, encrypted
transport replay envelopes, credentials or untrusted provider error strings.
Archive export requires the existing Data Lifecycle permissions and shared
archive storage protections; operators should still treat correlation
identifiers as sensitive.

**Hot cleanup, scheduled dispatch, and any destructive purge of hot rows are
NOT ADMITTED**. The policy UI permits Archive Only; both mutation/queue and
engine preflight reject unsupported cleanup, and the adapter itself refuses
direct cleanup. No automatic policy is created by GET. A manually enabled,
persisted policy may be used for explicit archive-only UAT after storage
readiness review. Repeated archive-only executions may produce overlapping
verified bundles; they do not relieve hot storage pressure yet. The existing
archive-retention purge contract still applies to expired archive *objects*.

The later #2850 safety foundation must implement durable dedup keys,
cross-domain Alert Incident deletion ownership, channel lifetime dependency
and source-linked historical aggregate preservation, with migration/backfill
and concurrency tests, **before** hot cleanup can be admitted. The operational
journal and Overview remain truthful only for committed hot state in this
phase (currently the complete delivery history). Archive History lists
artifact-level bundles only; it does not provide individual delivery lookup.

### Alert Incident compaction ownership guard (#2850 partial)

Alert Incident archive serialization retains a snapshot of firing/resolved
delivery outcomes in its verified case bundle. **Compaction must not delete
the canonical `NotificationDelivery` rows**, even for closed archived cases.
Those shared rows remain hot-owned by Notification Channels for replay
idempotency, retained evidence and channel deletion dependencies. Incident
compaction still clears incident-local case events, silences and heavy case
fields after archive verification; this is not a change to incident closure.

This source-ownership correction is only the first safety slice of #2850.
Durable post-hot-cleanup deduplication, historical aggregates, channel
dependency indexing and source record-level archive lookup are not admitted.
`notification_delivery` remains paused/manual archive-only.

## AuditEvent — paused manual archive-only boundary (#2890, 2026-10-23)

The **ninth** registered Data Lifecycle adapter `audit_event` governs the
`audit_events` table independently from `operational_activity` (shared
Notification-backed Activity Register), `job_execution`, and
`tenant_audit_evidence`. Access → Activity Audit Administrative Source
Evidence is only a **permission-scoped hot projection** of selected
`AuditEvent` producers; the archive domain is broader. Never treat these
sources as one store or duplicate committed rows in the Access UI.

This first implementation provides bounded ID/cutoff Preview, immutable
JSONL.GZ + manifest and shared checksum verification, but is **paused by
default** (no database policy row created by ordinary GET), manual only,
and **archive-only**. Fallback defaults 365 hot / 3650 archive days and
batch 250 are **proposals for operator review**, not an approved legal
retention policy. Source record count and hot evidence remain unchanged
after archive-only processing. Archive serialization stores only record
identity, nullable actor FK and sanitized target/action/summary/timestamp.
It intentionally omits free-form metadata, IP, user agent and any fabricated
immutable actor snapshot; such minimally redacted bundles **are not
sufficient evidence for hot cleanup**. Export/download of the bundles is
blocked until #2891 verifies producer-by-producer source permissions and
privacy. The Archive History view is artifact-level; no per-record cold
search is provided.

Server policy admission, queue admission, scheduled task, archive engine,
and domain adapter **all fail closed** on hot cleanup/scheduling. The
archive engine also rejects destructive archive-object purge for this
domain pending legal-hold/retention governance; the scheduled worker does
not auto-purge it during manual archive operation. This extension does
not modify the historical v1.3 baseline or the existing admitted domain
behavior. Related authority: foundation #2889, archive child #2890,
source-security and retention policy #2891, verified compaction and
permissioned archive lookup #2892. DevContainer functional/security UAT
and official gates remain pending.
