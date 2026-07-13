# KAORI Archive-First Retention Foundation

This package provides the shared lifecycle used by operational activity now and by login activity, reports, and future high-volume domains later.

## Safety invariants

1. Cleanup never starts until the data archive and manifest are uploaded and independently verified by size and SHA-256 checksum.
2. The archive selection is frozen by cutoff and maximum source ID.
3. Cleanup receives the exact `source.record_id` values read back from the verified JSONL archive, so later changes to source rows cannot expand the cleanup selection.
4. Jobs are serialized per domain with a PostgreSQL advisory lock; non-PostgreSQL development uses a process-local fallback lock.
5. Archive object keys are immutable because they contain the archive UUID.
6. Registry rows preserve a non-secret storage locator snapshot so archives remain addressable after the active Local/S3 profile changes.
7. Cleanup is batched and partial completion is retained as `cleanup_partial`; the verified archive is never removed automatically because cleanup failed.

## Artifact format

- Data: compressed JSON Lines (`.jsonl.gz`) for streaming and large datasets.
- Manifest: formatted JSON containing schema, selection boundary, record count, policy, storage locator, and data checksum.
- Registry: `archive_artifacts` stores lifecycle status, checksum, backend, object keys, counts, and execution metadata.

Every archived record must contain:

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

## Triggers

UI, CLI, and Celery Beat all call the same retention service.

```bash
flask archive-retention preview --domain operational_activity
flask archive-retention run --domain operational_activity --archive-only
flask archive-retention run --domain operational_activity --cleanup
flask archive-retention verify <archive-id>
flask archive-retention purge-archives --domain operational_activity
flask archive-retention purge-archives --domain operational_activity --execute
```

## Adding a future domain

1. Implement the `ArchiveDomain` protocol in `app/retention/domains/`.
2. Register the adapter in `DOMAIN_FACTORIES`.
3. Add domain-specific retention configuration.
4. Add the domain name to `ARCHIVE_SCHEDULED_DOMAINS` when scheduled cleanup is approved.
5. Add domain-specific RBAC and UI entry points while keeping archive/verify/cleanup logic in the shared service.

Planned adapters: login activity and generated report artifact lifecycle. Restore/import remains an administrative CLI concern and must include duplicate protection.

## Current operational activity semantics

The first adapter reads from the existing notification-oriented activity model. Its optional protection policy therefore maps "unreviewed" to `read_at IS NULL` for now. The UI labels this accurately as **Protected unread**. When KAORI introduces a dedicated immutable audit-event model with `reviewed_at` and `reviewed_by_user_id`, only the domain adapter should change; the shared archive, verification, registry, storage, cleanup, and scheduling services remain unchanged.
