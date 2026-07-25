# Platform Operations

Platform Operations contains cross-cutting operational control planes that are not routine Kubernetes resource CRUD.

## Navigation

- Jobs & Executions remains owned by `app/jobs/`.
- Kubernetes Administration is owned by `app/platform_operations/kubernetes/`.
- Advanced Kubernetes controls are exposed as tabs inside Kubernetes Administration.

## Kubernetes Administration

The first advanced control is Secret Reveal administration:

- cluster security readiness;
- namespace reveal policy;
- links to the protected one-time reveal workflow.

Operational Secret values remain owned by `app/kubernetes_operations/secrets/`. Platform Operations only owns the setup and policy boundary.

## Architecture Rules

- Do not add advanced Kubernetes setup back under Settings.
- Do not create proxy wrapper templates for ConfigMap or Secret UI components; import `kubernetes_operations/_components.html` directly.
- New advanced Kubernetes controls should use a dedicated tab and domain package under `app/platform_operations/kubernetes/`.
- Keep operational mutations, setup policy, and live Secret value access in separate modules.
