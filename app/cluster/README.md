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

## Protected Secret Reveal ownership

Cluster registration stores only the cluster identity, kubeconfig, and Kubernetes API TLS controls. Protected Secret Reveal readiness and namespace authorization are managed under **Settings > Secret Reveal** by users with `kubernetes_secrets.manage_reveal`.

The primary cluster kubeconfig remains the Kubernetes identity used by Reveal. Kubernetes administrators must scope that identity with least-privilege Role/RoleBinding grants. Do not add Reveal policy fields back to the Add/Edit Cluster form; cluster registration and sensitive-access governance are separate maintenance domains.
