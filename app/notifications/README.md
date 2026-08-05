# Notifications domain

Notifications is the central notification and administrative activity boundary for
KAORI. Feature modules use `app.notifications.service`; internal modules remain
implementation details.

## Structure

- `service.py`: public application use cases and orchestration.
- `writer.py`: persistence of normalized notification records.
- `queries.py`: notification-center and activity-audit reads, filters, and pagination.
- `normalization.py`: safe, user-friendly message and error normalization.
- `event_catalog.py`: event labels, module context, target context, source, and icons.
- `metadata.py`: metadata visibility, ordering, labels, and formatting.
- `presentation.py`: model-to-template transformation.
- `feedback.py`: low-level session feedback handling.
- `routes.py`: HTTP/HTMX boundary only.

## Dependency rule

Feature modules import public use cases from the service:

```python
from app.notifications.service import record_operational_activity
```

They must not directly import writer, query, feedback, presentation, metadata, or
event-catalog helpers. `service.py` owns normalization,
persistence retry behavior, feedback orchestration, and public use-case boundaries.

## Event contract

Stored `event_type` is the stable technical event key. The Activity Audit UI shows a
human-readable Event type only. The complete stored key, including prefixes such as
`operational_activity_`, appears under Operational metadata as **Event key**.

Do not duplicate `event_type` inside producer metadata; the presentation layer adds
Event key automatically. Keep event keys stable to preserve filters, historical
records, and integrations.

## Adding an event

1. Emit through `record_operational_activity()` or `create_notification()`.
2. Classify a new event family in `event_catalog.py`.
3. Add user-relevant metadata labels/formatting in `metadata.py`.
4. Add failure matching in `normalization.py`.
5. Never expose stack traces, SQL errors, transport exceptions, or raw payload dumps.
6. Store identifiers useful for audit; present readable labels separately.


## Notification Deck refresh boundary

Operational toast responses must never include top-bar navigation markup. They dispatch
the `kaori:notifications-changed` browser event instead. The bell trigger, teleported
slider shell, tabs, and Alpine-controlled sections are stable DOM boundaries and must
never be replaced by polling.

The deck uses one read-only status endpoint:

- `/notifications/panel/snapshot` returns Activity cards, Notification cards, unread
  count, and active-job count from one database snapshot.

The browser writes only into `#notification-deck-active-job-list` and
`#notification-deck-notifications-content`. The bell, drawer, tabs, selected state,
local foreground activities, and footer remain mounted. The endpoint uses
`Cache-Control: no-store`, and notification mutation responses retain HTMX out-of-band
badge synchronization.

Do not reintroduce `_notification_deck_content.html`, an `outerHTML` poll on the slider
root, a self-replacing fragment with a `load` trigger, or separate Activity and
Notifications polling requests.

## Activity Log visual standard

The Activity Audit Log uses the KAORI Violet Infrastructure presentation standard. The page hero and operational posture use KAORI Violet surfaces, while success, warning, failure, pending, and disabled states retain their semantic colors. Text labels use compact rectangular geometry (`rounded-md`) rather than pill geometry. Activity payloads, audit metadata, filters, HTMX pagination, retention execution, and lifecycle behavior are unchanged by this visual standard.


## Toast visual standard

Operational toast cards use KAORI Violet surface, border, typography, and action
styles. Semantic status colors are limited to the status accent, icon, and status
label. The progress or completion rail is a separate narrow element below the toast
card; it must not be absolutely attached to the card edge. This separation keeps the
operation state visible without making the toast look like a single fused block.

Personal preference saves do not generate operational toasts. They create personal
Notification Center records and trigger the canonical notification refresh event.

## Notification Deck standard

KAORI uses one synchronized source across:

- one persistent top-bar notification bell;
- the right-side Notification Deck; and
- `/notifications/`, the full personal notification page.

Do not add a second Activity icon to the top bar. The bell badge represents unread
`Notification` rows only. A small violet dot on the bell indicates that one or more
`JobExecution` or local foreground operations are active; it does not change the unread
badge count. Both indicators are absolutely positioned so header width never changes.

The bell opens a full-height slide-over deck from the right with two sections:

- **Activity** shows canonical jobs and short-lived in-browser HTMX operations.
- **Notifications** shows the same persistent records used by the full Notifications page.

Opening the deck does not mark records as read. Records become read only through an
explicit item action or **Mark all read**. Background refresh replaces only the inner contents of the stable Activity and
Notifications sections. It never replaces the bell, navbar, slider shell, tabs, or
Alpine state, so polling cannot make controls flicker or leave a blank panel.

## Operational delivery policy

KAORI separates three responsibilities:

- **Operational toast** provides immediate feedback for the request currently being performed.
- **Notification Deck** is a persistent operational inbox for outcomes that remain actionable after navigation.
- **Activity Audit** is the authoritative historical record and includes Deck-visible and audit-only events.

`OperationalDeliveryPolicy` defines persistence visibility:

- `audit_only` persists Activity Audit evidence but hides the row from Notification Deck.
- `deck_on_failure` hides successful outcomes and shows warning/error outcomes in Notification Deck.
- `persistent` shows every terminal outcome in Notification Deck.

`notifications.deck_visible` is the canonical boundary. Notification Deck queries must filter
`deck_visible = true`; the administrative Activity Audit query must continue reading all rows.
Audit-only rows are written as read so they never inflate unread counters.

Foreground policy for ConfigMap, Secret, and TLS operations:

| Event | Toast | Notification Deck | Activity Audit |
|---|---:|---:|---:|
| Validation/dry-run result | Yes | No | No |
| ConfigMap/Secret create or replace success | Yes | No | Yes |
| ConfigMap/Secret create or replace warning/failure | Yes | Yes | Yes |
| ConfigMap/Secret delete terminal result | Yes | Yes | Yes |
| Secret reveal request/approval/denial | Yes | Yes | Yes |
| One-time Secret reveal completion | Yes | No | Yes |
| TLS Secret rotation terminal result | Yes | Yes | Yes |
| TLS inventory sync queued | Progress toast / JobExecution | No | Dispatch audit |
| TLS inventory sync terminal result | Yes when the page is active | Yes | Yes |

Background progress is owned by `JobExecution` and the canonical operational progress toast.
Successful dispatch must not create a duplicate queued Notification row. The worker persists the
terminal Activity Audit event and requester Notification Deck row before changing the JobExecution
to its terminal state, so polling cannot stop before the persistent evidence is committed.

`queue_transient_feedback()` never persists a Notification row. Use it only for validation, queued
acknowledgement, and other request-local feedback. Never place Secret values, ConfigMap values,
private keys, certificate bytes, tokens, stack traces, or raw provider payloads in toast, Deck, or
Activity Audit metadata.

### Slider deck viewport boundary

The Notification Deck is rendered through Alpine `x-teleport="body"`. The bell remains in the top navigation, while the dialog is moved to the document body. This is mandatory because the sticky navigation uses backdrop filtering, which creates a containing block and can otherwise clip a `position: fixed` drawer to the navbar height.

The deck uses only utilities present in the committed Tailwind build: `fixed inset-0`, `bg-surface-overlay/70`, and `max-w-md`. Do not replace these with uncompiled arbitrary values without rebuilding `app/static/css/output.css`.

### Notification Deck tab and refresh standard

The deck and `/notifications/` use the same segmented-control geometry as the
Reports **Report Type Guide**: a violet-soft `rounded-xl` track with compact
`rounded-lg` text tabs, a white active surface, and no oversized tab cards.
Activity and Notifications remain separate semantic views but share one visual
contract.

The Activity panel must always render one of the following: local foreground
activity, canonical `JobExecution` cards, or the explicit empty state. Inventory
synchronization is not rendered through a second nested polling source; it remains
part of the canonical job list. This prevents activity cards from disappearing and
reappearing whenever the panel refreshes.

The **Quick Actions → Sync All Inventory** workflow only dispatches the canonical
worker job. Clicking the action closes Quick Actions but never opens the Notification
Deck, changes its selected tab, creates a local foreground Activity card, or forces an
immediate snapshot request. The button may show request-local disabled/spinner feedback
while the enqueue HTTP request is in flight; this is not Activity Center state.

The Activity tab is updated exclusively from committed `JobExecution` rows through the
normal 15-second snapshot cycle. Successful dispatch does not create a duplicate
"queued" notification because the job row is already the authoritative activity source.
Blocked, skipped, and failed dispatches remain persistent Notifications and appear on the
next automatic snapshot. Never target the removed `#quick-sync-feedback` element or
reintroduce a forced drawer-open/event-refresh flow.

Activity and Notifications use one read-only JSON snapshot every 15 seconds. The
snapshot reads current `JobExecution` and `Notification` rows only; it never waits for
a queued or running worker to complete. Opening the deck also requests a snapshot so
the user does not wait for the next interval. The response updates the two stable
content slots and counters in place, while the drawer, selected tab, local foreground
activity, and bell remain mounted.

The deck has no manual refresh button, spinner, or manual-refresh state. Automatic
polling is silent and allows only one request at a time. If an event-driven refresh
arrives while a snapshot is in flight, KAORI queues exactly one follow-up snapshot
instead of dropping the event or starting an overlapping request. Native `fetch()`
uses `AbortController` with a five-second request boundary so a stalled request cannot
block later intervals. On failure, existing
content remains visible and the footer shows a quiet reconnecting state; no toast or
blocking error is emitted. A queued job remains visible as **Queued / Waiting** with a
static progress marker and never controls polling state.
