# KAORI Data Lifecycle Foundation

This package provides the shared archive-first lifecycle used by **Platform Operations → Data Lifecycle**. The engine is domain-neutral: each source table supplies a small adapter, while policy persistence, archive writing, checksum verification, cleanup, scheduling, storage, canonical jobs, notifications, and execution history remain shared.

## Current managed domains

- `operational_activity`: canonical Activity Audit records.
- `job_execution`: terminal canonical worker executions and subscriber snapshots.
- `runtime_observation`: append-only integration runtime observation history.

Future domains such as generated reports, analytics datasets, and forecast results should be added as adapters rather than separate retention subsystems.

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

Celery Beat runs a lightweight dispatcher every 15 minutes. Persistent per-domain policies decide whether a domain is due and at what hour/minute. Due domains are fanned out as separate maintenance jobs, so Activity Audit and Job Execution retention do not create one large database/storage burst.

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
- Archive Storage
- Archive History

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

`integration_runtime_observations` is an active `runtime_observation` lifecycle domain. Runtime writes are append-only and no longer delete older rows through a per-connection rolling limit. Hot retention, archive verification, and cleanup are controlled centrally from **Platform Operations → Data Lifecycle**. The default policy keeps 90 days in PostgreSQL, retains verified archives for 365 days, and schedules the domain separately from Activity Audit and JobExecution.
