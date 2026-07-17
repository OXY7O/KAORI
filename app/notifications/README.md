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
event-catalog helpers. `service.py` is not a re-export facade; it owns normalization,
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


## Notification Center refresh boundary

Operational toast responses must never include the full Notification Center markup.
They dispatch the `kaori:notifications-changed` browser event instead. The single
canonical `#notification-center` instance in the navbar listens for that event and
refreshes itself from `notifications.panel` using `outerHTML`. This prevents duplicate
notification bells from being appended beside or below toast containers.
## Activity Log visual standard

The Activity Audit Log uses the KAORI Violet Infrastructure presentation standard. The page hero and operational posture use KAORI Violet surfaces, while success, warning, failure, pending, and disabled states retain their semantic colors. Text labels use compact rectangular geometry (`rounded-md`) rather than pill geometry. Activity payloads, audit metadata, filters, HTMX pagination, retention execution, and lifecycle behavior are unchanged by this visual standard.

