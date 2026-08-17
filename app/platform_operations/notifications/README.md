# Notifications domain

Notifications is the central notification and administrative activity boundary for
KAORI. Feature modules use `app.platform_operations.notifications.service`; internal modules remain
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
from app.platform_operations.notifications.service import record_operational_activity
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
2. Classify a new event family in the source-controlled `app/definitions/catalogs/platform_operations/notifications/event_categories.yaml`; `event_catalog.py` loads and validates that contract.
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

## Activity Audit evidence-store boundary

Activity Audit HTTP routes and templates are Access-owned under `app/access/activity_audit/`. `app/platform_operations/notifications/` owns the shared operational evidence persistence/query kernel used by Activity Audit and Notification Center. Each persisted row snapshots its event category and actor identity so later catalog changes, user renames, role changes, or user deletion do not rewrite historical evidence.


## Toast visual standard

Operational toast cards use KAORI Violet surface, border, typography, and action
styles. Semantic status colors are limited to the status accent, icon, and status
label. The progress or completion rail is a separate narrow element below the toast
card; it must not be absolutely attached to the card edge. This separation keeps the
operation state visible without making the toast look like a single fused block.

Personal preference saves generate the standard immediate toast and durable Activity Audit evidence, but remain hidden from Notification Center because routine display/locale preferences are not actionable operational outcomes.

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

- **Active Work** shows canonical jobs and short-lived in-browser HTMX operations.
- **Notifications** shows the same persistent records used by the full Notification Center page.

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

Foreground policy follows `docs/design/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md`. The key ConfigMap, Secret, and TLS rules are:

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

The deck uses a compact neutral segmented control; the full `/notifications/` page uses the KAORI framed workspace-tab geometry. Brand color is limited to the active label and small accents, while the track uses semantic surface tokens so dark mode remains quiet. The two user-facing views are **Notifications** and **Active Work**; the word **Activity** is reserved for the administrative Activity Audit context rather than used as a user-inbox tab label.

The Active Work panel must always render one of the following: local foreground
activity, canonical `JobExecution` cards, or the explicit empty state. Inventory
synchronization is not rendered through a second nested polling source; it remains
part of the canonical job list. This prevents activity cards from disappearing and
reappearing whenever the panel refreshes.

The **Quick Actions → Sync All Inventory** workflow only dispatches the canonical
worker job. Clicking the action closes Quick Actions but never opens the Notification
Deck, changes its selected tab, creates a local foreground Activity card, or forces an
immediate snapshot request. The button may show request-local disabled/spinner feedback
while the enqueue HTTP request is in flight; this is not Activity Center state.

The Active Work tab is updated exclusively from committed `JobExecution` rows through the
normal 15-second snapshot cycle. Successful dispatch does not create a duplicate
"queued" notification because the job row is already the authoritative activity source.
Blocked, skipped, and failed dispatches remain persistent Notifications and appear on the
next automatic snapshot. Never target the removed `#quick-sync-feedback` element or
reintroduce a forced drawer-open/event-refresh flow.

Active Work and Notifications use one read-only JSON snapshot every 15 seconds. The
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

## Full Notification Center page

`/notifications/` remains a dedicated personal operational inbox because it serves a different audience and purpose from **Activity Audit**. The hero uses the standardized **Notification Posture** context panel. The Notifications workspace presents **Notification Evidence** before the register, then uses shared KAORI search/category/status/state filters, the shared loading bar, and the table contract with `Notification / Event / Status / Received / State / Action` columns.

Default Rows is 5 with 5/10/25/50 choices. Pagination must render **Previous**, numeric pages, and **Next**, and every HTMX refresh/read/pagination action must preserve the active filter state. Compact Notification titles and event labels use Title Case with operational acronyms preserved. Category labels are `ConfigMap Management`, `TLS Certificate`, `Secret Management`, `Integrations`, `Platform Operations`, `Access`, and `Settings`.

The page is login-scoped and shows only deck-visible records targeted to the current user. **Active Work** mirrors canonical `JobExecution` state and links to Jobs & Executions for full evidence; it never becomes a second execution registry. Activity Audit remains permission-gated and system-wide.

Persistent Notification Center rows and Activity Audit rows share the `notifications` table and therefore the same **Platform Operations → Data Lifecycle → Activity Audit** archive-first policy. Audit-only rows remain outside the personal inbox through `deck_visible=false` but are still lifecycle-managed. Transient request-local toasts are not persisted and remain outside Data Lifecycle.

## Activity Audit refinement boundary

Activity Audit is the permission-gated, system-wide administrative evidence view. Its hero and overview use bounded 24-hour posture, while the register defaults to a seven-day retained window and supports Category, Status, Actor, Time Range, and free-text search filters. Read/unread state remains a Notification Center delivery concern and is intentionally absent from Activity Audit.

The Activity Register uses shared KAORI loading, table, status-label, modal, and pagination components. Activity details expose normalized actor, target, change, and curated operational metadata only. Sensitive keys such as passwords, raw Secret values, tokens, private keys, kubeconfig content, and credential values are suppressed defensively even though producers are already required not to persist them.
