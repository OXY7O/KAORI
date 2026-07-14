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


## Protected Secret Reveal cluster controls

Cluster registration owns the per-cluster security gates for Protected Secret Reveal. Editing these fields requires `kubernetes_secrets.manage_reveal`; `clusters.manage` alone is insufficient:

- `secret_reveal_policy`: `disabled`, `step_up`, or `approval_required`;
- Protected Reveal uses the cluster's primary kubeconfig identity; Kubernetes administrators must restrict its ServiceAccount/user with the minimum required verbs and namespace scope;
- `secret_reveal_encryption_verified`: operator attestation for Kubernetes Secret encryption at rest;
- `secret_reveal_audit_verified`: operator attestation that Secret reads are audited at Metadata level without request/response bodies.

A non-disabled policy is rejected unless both security attestations are present. Reveal uses the same kubeconfig as inventory and Kubernetes operations; KAORI does not store a second credential. The Kubernetes cluster administrator must therefore review the ServiceAccount/user permissions whenever an operation is enabled and prefer namespace-scoped Role/RoleBinding grants.

Cluster activity metadata may record policy and that the cluster kubeconfig model is in use, but it must never contain kubeconfig content or authentication material. The global feature switch remains in application configuration, while cluster policy remains in the database so production, development, and restricted clusters can use different controls.
