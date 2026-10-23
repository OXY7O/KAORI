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

## Notification Delivery archive-only extension (#2848, 2026-10-23)

Current registry adds `notification_delivery` as an **additional,
non-destructive** domain after the historical v1.3 baseline. This note does
not retroactively claim v1.3 approved its execution. Its single authority
remains Platform Operations → Data Lifecycle, reusing the existing
ArchiveDomain interface, policy, shared storage, verification and Jobs.

The first admission keeps a paused 90/365-day policy (proposal), manual
archive-only operation, bounded 1,000 record reads, and terminal `sent`/
`skipped` candidates older than both created and last-updated cutoffs.
Provider payload and encrypted retry envelope never enter the new archive.
No automatic scheduling, delete, channel-dependency release or changed
all-time count is allowed. Cleanup is server-rejected before archive execution
and separately prohibited in the domain adapter. Per-record archive browsing
is not supported; Archive History remains artifact-level.

Follow-up #2850 must reconcile existing Alert Incident cleanup cross-domain
deletes before enabling hot cleanup, while separately governing permanent
deduplication and historical cumulative evidence. Manual DevContainer UAT,
security review and official admission gates remain pending.

### Source ownership refinement — Alert Incident / Notification Delivery (#2850 partial)

An Alert Incident archive may include a verified snapshot of its related
delivery outcomes, but that does **not** confer delete authority over the
shared `notification_deliveries` table. Alert Incident compaction must not
delete `NotificationDelivery` rows. Only a separately admitted
`notification_delivery` lifecycle with durable deduplication and retained
cumulative evidence could safely compact or delete the hot journal.
The present adapter remains archive-only and paused. This guard does not
claim that the full #2850 cleanup foundation or runtime UAT has passed.

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
