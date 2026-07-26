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

## Kubernetes Administration workspace contract

- The landing page owns the canonical hero, one administration overview surface, and internal Alpine tabs directly below the overview surface.
- Overview and Secret Reveal tab changes must not reload the page. The selected tab updates browser history with `history.replaceState`; Secret Reveal loads its heavier cluster and namespace workspace lazily through HTMX only when the tab is opened. Both tabs remain directly addressable through `?tab=overview` or `?tab=secret-reveal`.
- The Secret Reveal legacy route redirects to the consolidated Kubernetes Administration workspace so bookmarks and notification links remain compatible.
- The Overview tab lists only production-ready controls as available. Recommended future domains are guidance, not enabled features: RBAC posture review, maintenance controls, admission and policy governance, and protected resource actions.
- New administration domains should become isolated tab workspaces only after their permission, validation, audit, rollback, and ownership boundaries are implemented.
