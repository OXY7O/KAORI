# Notifications domain

The notifications package is KAORI's central operational-notification domain. It supports two related views while keeping their responsibilities separate:

- Notification Center: a compact, per-user stream in the top navigation.
- Activity Audit Log: an administrative, cross-user audit workspace.

## Module boundaries

- `writer.py` — notification persistence and operational-activity recording.
- `queries.py` — navigation and audit-log queries, filters, pagination, and read state.
- `presentation.py` — serialization of notification models into template-ready data.
- `event_catalog.py` — event-family classification, target/module labels, icons, and source context.
- `metadata.py` — metadata labels, formatting, ordering, change detection, and visibility rules.
- `normalization.py` — user-friendly text normalization and raw-error suppression.
- `feedback.py` — quick-action feedback payloads and redirect-session lifecycle.
- `constants.py` — shared status, pagination, and display limits.
- `routes.py` — HTTP/HTMX orchestration only; domain logic remains in focused modules.

There is intentionally no `service.py` facade. Feature modules import the focused module they use directly so ownership remains explicit and no wrapper layer obscures the dependency graph.

Inside the `app.notifications` package, use relative imports such as `from .writer import ...`. Feature modules outside the package use direct imports such as `from app.notifications.writer import ...`.

## Extension rules

1. Use `writer.py` for `record_operational_activity()` and `create_notification()`.
2. Use `queries.py` for notification-center and activity-log reads.
3. Use `feedback.py` for quick-action feedback state.
4. Add event-family presentation rules to `event_catalog.py`, not route files or templates.
5. Add metadata labels and formatting rules to `metadata.py`.
6. Add raw-error mappings to `normalization.py`; do not expose exception strings in user-facing notifications.
7. Keep route handlers focused on request validation, authorization, orchestration, and response rendering.
8. Notification persistence failures must not convert a successful primary operation into a failed operation.
