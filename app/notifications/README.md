# Notifications domain

The notifications package is the central notification and administrative activity
boundary for KAORI. Feature modules use `app.notifications.service` only; package
internals remain private implementation details.

## Structure

- `service.py` — application use cases and the public notification-domain API.
- `writer.py` — database persistence for already-normalized notification records.
- `queries.py` — notification-center and activity-audit queries, filtering, and pagination.
- `normalization.py` — safe, user-friendly message and error normalization.
- `event_catalog.py` — event labels, concise event codes, module context, target context, and icons.
- `metadata.py` — metadata visibility, labels, ordering, and value formatting.
- `presentation.py` — conversion from database models into template-ready objects.
- `feedback.py` — low-level session feedback storage and payload construction.
- `routes.py` — HTTP/HTMX request handling only.
- `constants.py` — shared domain constants.

## Dependency rule

Feature modules must import notification use cases from the service:

```python
from app.notifications.service import record_operational_activity
```

They must not import `writer.py`, `queries.py`, `feedback.py`, or presentation helpers
directly. Inside this package, use relative imports.

The intended dependency direction is:

```text
feature / route / task
        -> service.py
        -> normalization / queries / feedback
        -> writer / presentation / event_catalog / metadata
        -> database model
```

`service.py` is not a re-export facade. It owns notification normalization,
persistence retry behavior, audit feedback orchestration, and the public use-case
boundary. `writer.py` intentionally performs persistence only.

## Adding an event

1. Emit the event through `record_operational_activity()` or `create_notification()`.
2. Add module and target classification in `event_catalog.py` when a new event family is introduced.
3. Add metadata labels or formatting in `metadata.py` when new metadata is user-relevant.
4. Add raw failure matching in `normalization.py`; never expose stack traces or transport exceptions to users.
5. Keep the stored event type stable. Presentation may remove internal prefixes, such as `operational_activity_`, without changing stored data or filter values.
