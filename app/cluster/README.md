# Cluster domain

Cluster owns Kubernetes cluster registration, onboarding, configuration lifecycle,
connection validation, and inventory-sync orchestration.

## Boundaries

- `service.py`: cluster lifecycle use cases.
- `onboarding.py`: onboarding-specific validation and preparation.
- `sync_state.py`: user-visible sync state and progress.
- `tasks.py`: Celery entrypoints for background sync.
- `routes.py`: forms, access control, and HTMX responses only.

Cluster actions that affect configuration or execution must emit centralized
notifications through `app.notifications.service`. Connection failures must be
translated into user-friendly messages while raw exceptions stay in application
logs. Background sync must continue across page navigation and remain idempotent.
