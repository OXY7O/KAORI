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
the `kaori:notifications-changed` browser event instead. The bell trigger remains a
stable DOM element; only canonical `#notification-deck-content` is refreshed from
`notifications.panel`. Badge and running-indicator values are updated through HTMX
out-of-band swaps.

The self-replacing deck content uses `every 15s` and must never use an additional
`load` trigger. Combining `load` with `outerHTML` replacement causes a refresh loop,
visible flicker, and navigation controls that appear and disappear.

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
explicit item action or **Mark all read**. Background refresh replaces only the deck
content, never the bell or the navbar, so polling cannot make top-bar controls flicker.

## Toast delivery policy

Background progress and normal background completion must use the Activity Center,
not stacked toast cards. `record_operational_activity()` automatically routes events
with job references or background-event semantics to `activity_center` delivery.

Toast remains appropriate for immediate interruption feedback:

- validation failures;
- permission denial;
- destructive-action outcomes;
- session/security issues; and
- foreground warning or error conditions that affect the action the user is currently taking.

Warning or error outcomes tied to a background job still use Activity Center delivery;
they raise the bell/Attention count instead of creating stacked toasts. Callers may set
`metadata.feedback_delivery` to `toast` only when a background outcome must interrupt
the current screen.

`queue_transient_feedback()` always remains toast-based because it is non-persistent
and represents immediate request feedback. Background events still persist a
`Notification` row and dispatch `kaori:notifications-changed`, even when no toast is
rendered.
