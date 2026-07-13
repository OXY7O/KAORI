# Notifications domain

The notifications package is the central operational-notification domain for KAORI.
It supports two related views without coupling their responsibilities:

- Notification Center: a compact, per-user stream in the top navigation.
- Activity Audit Log: an administrative, cross-user audit workspace.

## Module boundaries

- `service.py` — stable public facade used by the rest of the application.
- `writer.py` — notification persistence and operational-activity recording.
- `queries.py` — navigation and audit-log queries, filters, pagination, and read state.
- `presentation.py` — serialization of notification models into template-ready data.
- `event_catalog.py` — event-family classification, target/module labels, icons, and source context.
- `metadata.py` — metadata labels, formatting, ordering, change detection, and visibility rules.
- `normalization.py` — user-friendly text normalization and raw-error suppression.
- `feedback.py` — quick-action feedback payloads and redirect-session lifecycle.
- `constants.py` — shared status, pagination, and display limits.
- `routes.py` — HTTP/HTMX orchestration only; domain logic remains in focused modules.

## Extension rules

1. Producers should call `record_operational_activity()` or `create_notification()` through `service.py`.
2. Add event-family presentation rules to `event_catalog.py`, not route files or templates.
3. Add metadata labels and formatting rules to `metadata.py`.
4. Add raw-error mappings to `normalization.py`; do not expose exception strings in user-facing notifications.
5. Keep route handlers focused on request validation, authorization, orchestration, and response rendering.
6. Notification persistence failures must not convert a successful primary operation into a failed operation.
