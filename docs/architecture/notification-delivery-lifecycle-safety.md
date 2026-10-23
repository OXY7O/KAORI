# Notification Delivery: Durable Identity and Safe Archive-First Compaction

**Design workstream:** [#2868](https://github.com/OXY7O/KAORI/issues/2868)
under [#2850](https://github.com/OXY7O/KAORI/issues/2850) and [#2847](https://github.com/OXY7O/KAORI/issues/2847).
**Status:** proposed migration/rollout contract for review; not a claim of admitted or
executed database changes. **Current hot cleanup remains prohibited**.

## Source authority and cross-domain ownership

- Notification Channels is owner of `notification_deliveries`, outbound
  credential/policy admission, immutable encrypted replay envelope, attempt
  status and provider acknowledgment. External provider owns transport.
- Alert Incident retains its own incident and a *snapshot* of correlated
  delivery outcomes in incident archives; incident compaction never deletes
  `notification_deliveries` (#2850 first safety slice).
- Platform Operations Data Lifecycle owns archive policy, checksummed bundle,
  retention and governed cleanup. Current `notification_delivery` adapter
  is **paused**, manual, archive-only and `cleanup_supported = False`.
- An event may fan out into several channels. Unique idempotency scope is
  `(channel_id, event_key)`, not global `event_key`.
- Activity Audit remains business-action evidence, not a notification delivery
  callback. CDEvents SDLC Delivery Intelligence #536 is a separate product.

## Current correctness dependencies

1. `notification_deliveries` itself owns the only unique event/channel
   reservation. Removing it can permit a duplicate send.
2. Channel hard-delete uses delivery history to enforce evidence dependency.
   Deleting hot rows can unlock forbidden deletion unless archived identity
   is counted by a separate authoritative relation.
3. Overview counts current delivery status directly from live SQL groups.
   Purging old hot records silently reduces all-time outcome totals.
4. `failed` can be retryable. `queued` can represent a committed in-flight
   transport attempt. The first archive-only adapter selects aged `sent` /
   `skipped` while retaining all source rows.
5. #1475 adds nullable `next_retry_at` to keep provider 429 deadlines
   independent of `updated_at`. Legacy NULL rows follow the established
   retry minimum. It does not grant cleanup or recovery activation.

## Proposed durable identity ledger (#2868)

Define a compact table with a unique index over
`(channel_id, event_key)`, immutable first-seen identity, canonical
source domain/type/key, and a stable delivery identity. Do **not** copy
the provider message payload, credentials, encrypted replay snapshot,
raw error or destination URL into this ledger.

Requirements:

- A ledger reservation and initial `NotificationDelivery` journal insertion
  must be committed **atomically before sending**. An already-reserved
  key must resolve to the canonical pending/sent/archived identity and must
  not create a second network attempt.
- A worker crash between reservation and transport must remain recoverable
  from the journal; the ledger must not incorrectly assert delivery success.
- Only an explicit new versioned lifecycle policy may expire tombstones
  after a bounded idempotency horizon. Default is **retain**, until the
  security/data-governance decision defines and accepts an expiry policy.
- Channel deletion constraints must account for ledger/archive references
  and report schedules; do not cascade-delete durable identities.
- Backfill must be resumable and bounded by ID/cursor, with a persisted
  progress/fence and conflict report. Do not synthesize absent delivery facts.
- A mixed-version dual-write rollout is unsafe without version fencing.
  Require deployment compatibility review and explicit backfill completion
  proof before permitting any cleanup.

## Cumulative outcome and dependency materialization (#2869)

Model committed, source-owned counts separately from individual attempts:
one event/channel identity may contain several send attempts and status
transitions. The counted state is the **current final outcome of each
committed identity**, updated transactionally as status changes. Maintain
clearly separate metrics for attempts if genuine attempt history exists.

Required reconciliation: `hot + verified-archived identity coverage`
must equal aggregate eligible identity count, with no overlap/double-count.
Prove per-channel dependency invariants for active/retired channels, report
schedule retention, and total outcomes after moving hot rows to archive.
Historical counts need stable status/as-of definitions; `updated_at`
cannot be quietly reinterpreted as end-user receipt time.

For analytics (#2863/#2864), define versioned read models by provider,
channel, event domain/type and time window only after these aggregates
are source-qualified. Expose `Unknown`, `Incomplete` and source freshness
instead of fabricated zeros or guessed send latency.

## Verified cleanup and archive search admission (#2870)

Cleanup remains impossible while `cleanup_supported=False`. To change
that flag, require all of the following on an exact pinned SHA and database
revision:

1. A tested durable identity ledger and checksum-verified backfill.
2. Materialized historical outcomes and per-channel dependencies with
   reconciled parity against the hot journal and verified archive.
3. Stable ID/cutoff archive selection, verified archive object digest,
   non-sensitive archive representation and governed retention.
4. Concurrency fencing: in-flight/queued/retryable records excluded,
   no race with dispatch/recovery (including #1475 future retry deadline).
5. Idempotent bounded transactional compaction and crash/restart resume;
   retain audit/provenance for every removed hot source identity.
6. A permissioned archive index read model; source links are only exposed
   after source and role checks. No implicit raw bundle download permissions.
7. A preview/dry-run first, plus explicit operator acceptance, rollback
   and backup/restore procedure, performance budget and DAST/security UAT.

Do not advertise historical browsing as a live capability before this
index and source-authorization contract exist. Archive History currently
lists **bundles**, not per-delivery records.

## Required adversarial UAT matrix

| Scenario | Required outcome |
| --- | --- |
| Two producers emit same channel/event concurrently | One committed identity; never a duplicate network send from reservation race |
| Provider accepted, worker crashed before outcome commit | Unknown-at-least-once state; bounded recovery, never claim exactly once |
| HTTP 429 with future Retry-After | No send/claim before persisted due timestamp |
| Backfill interrupted or conflicts with new traffic | Resume safely with parity, no false completed generation |
| Attempted cleanup of queued / failed retry-eligible row | Hard DENY with no hot deletion |
| Archive object missing/corrupted or checksum mismatch | Hard DENY cleanup; audit failed verification |
| Hot row purged but ledger retained | Event redelivery still suppressed according to approved policy |
| Channel retired with archived delivery dependency | Remains read-only/locked; no evidence lost |
| Repeated archive job covers same source identity | No double-count and no false archive readiness |
| Missing provider/asset permission on archived lookup | No source payload/link disclosure |
| Large journal dataset and constrained DB indexes | Bounded latency, stable pagination and incremental backfill |
| Legacy NULL retry deadline | Retains documented global retry delay |

## Rollout and status gates

`Issue #2868 (identity) → #2869 (aggregates) → #2870 (cleanup/index) →
targeted DevContainer UAT → explicit human acceptance → authorized
official Developer Check/Full Admission → staging UAT → main`.

Use existing Alembic, SQLAlchemy, canonical JobExecution, Data Lifecycle
adapter, and shared archive verification; **no custom mutation framework**.
Store exact SHAs, schema revision, SQL row-count/digest parity, source
coverage, failure-injection evidence and reviewer decision per workstream.

As of this design note, **no new ledger, aggregate schema, archive index
or hot cleanup has been implemented or admitted**. This document defines
a reviewable and testable boundary, not authorization for migration, purge
or scheduled recovery.
