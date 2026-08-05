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
- Do not create proxy wrapper templates for ConfigMap or Secret UI components; import `components/kubernetes_operation_ui.html` directly.
- New advanced Kubernetes controls should use a dedicated tab and domain package under `app/platform_operations/kubernetes/`.
- Keep operational mutations, setup policy, and live Secret value access in separate modules.

## Kubernetes Administration workspace contract

- The landing page owns the canonical hero, one administration overview surface, a standalone Jobs & Executions-style violet tab surface, and the active workspace below it. Canonical `space-y-6` gaps must separate all four layers so no surface visually collides.
- The hero context panel follows Jobs & Executions geometry: one header, two metric cards, and one compact status strip below the metrics.
- Every Secret Reveal workspace response must have a single `space-y-6` root. Protection posture, global warning, cluster readiness, and namespace policy surfaces must remain separate blocks rather than adjacent unspaced siblings.
- Overview and Secret Reveal tab changes must not reload the page. The selected tab updates browser history with `history.replaceState`; Secret Reveal loads its heavier cluster and namespace workspace lazily through HTMX only when the tab is opened. Both tabs remain directly addressable through `?tab=overview` or `?tab=secret-reveal`.
- The Secret Reveal legacy route redirects to the consolidated Kubernetes Administration workspace so bookmarks and notification links remain compatible.
- The Overview tab lists only production-ready controls as available. Recommended future domains are guidance, not enabled features: RBAC posture review, maintenance controls, admission and policy governance, and protected resource actions.
- New administration domains should become isolated tab workspaces only after their permission, validation, audit, rollback, and ownership boundaries are implemented.

- Kubernetes Administration tabs use the same compact rounded-button treatment as the Jobs & Executions inner workspace tabs: violet soft container, active violet button, and inactive white button with violet border.
- Secret Reveal readiness and namespace policy saves update only the Secret Reveal cluster workspace through HTMX; full-page redirects are fallback behavior only.
