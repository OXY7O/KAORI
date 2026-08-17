# KAORI Activity Audit Final Recheck — 2026-08

Status: **PASS — Activity Audit Final Lock v1**

## Locked ownership

- `app/access/activity_audit/` owns the Access HTTP and presentation workspace.
- `app/notifications/` owns the shared persisted operational evidence store and query/presentation kernel.
- `app/retention/domains/operational_activity.py` owns archive-first lifecycle and cleanup.
- No `/notifications/activity` compatibility route or Notification-owned Activity template remains.

## Evidence boundaries

- `user_id` is notification recipient/target context and is not actor identity.
- `actor_key`, `actor_label`, and `actor_snapshot_json` are committed with the event.
- failed authentication uses an unauthenticated actor snapshot and never claims the resolved target account as actor.
- background activity without an authenticated request is attributed to **KAORI System** unless explicit actor metadata resolves to a user.
- the recipient FK uses `ON DELETE SET NULL`, so user lifecycle cannot cascade-delete operational evidence.
- event `category_key` is persisted from the source-controlled notification category catalog.

## Hot and archive semantics

The Activity Register reads hot PostgreSQL rows only. The broadest time option is **All Hot Records**. Verified older evidence remains under Platform Operations → Data Lifecycle archive history. Operational Activity archive schema v2 copies the immutable actor snapshot already stored with the source row and does not join the live User table during archive serialization.

## UX decision

Activity Audit remains one workspace rather than a tabbed page. Search/filter/table and the content-driven detail modal form one evidence-review workflow; adding tabs would hide evidence without introducing a distinct lifecycle or mutation concern.
