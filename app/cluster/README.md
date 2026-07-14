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
- `secret_reveal_kubeconfig`: optional dedicated credential, never displayed back to the browser;
- `secret_reveal_encryption_verified`: operator attestation for Kubernetes Secret encryption at rest;
- `secret_reveal_audit_verified`: operator attestation that Secret reads are audited at Metadata level without request/response bodies.

A non-disabled policy is rejected unless all prerequisites are present. The dedicated kubeconfig is parsed and must target the same Kubernetes API server as the primary cluster kubeconfig. Editing with no upload retains the current reveal credential. The explicit **Revoke dedicated reveal credential** control removes it only while policy is Disabled.

Cluster activity metadata may record policy and whether a credential is configured, but it must never contain kubeconfig content or authentication material. The global feature switch remains in application configuration, while cluster policy remains in the database so production, development, and restricted clusters can use different controls.
