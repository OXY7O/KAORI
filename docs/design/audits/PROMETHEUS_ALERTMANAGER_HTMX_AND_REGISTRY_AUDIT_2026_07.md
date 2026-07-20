# Prometheus and Alertmanager HTMX, Feedback, and Registry Audit — July 2026

## Scope

The audit reviewed normal user flows for Prometheus and Alertmanager:

- Provider landing page and connection registry.
- Connection registration.
- Configuration, validation, runtime, scope, binding, and deletion actions.
- Provider registry filtering and pagination.
- Operational scopes without an eligible provider source.
- Route references that still forced cluster compatibility pages.
- Prometheus instance-detail context safety.

## Findings

### Feedback and page reload drift

Several same-page actions persisted Activity Audit events but redirected and reloaded the entire provider workspace. Other actions returned HTMX partials without returning the matching toast payload. Binding removal and instance deletion were the most visible inconsistencies.

### Registry parity drift

Prometheus used Compatibility, Environment, and Readiness filters while Alertmanager used Search, Readiness, and Connection Type. Prometheus pagination used a larger footer font and did not consistently push filter state to the browser URL.

### Uncovered scope placement

Prometheus displayed uncovered scopes inside the registry component and Alertmanager did not expose uncovered scopes. This mixed scope readiness with connection filtering and prevented both providers from using the same information architecture.

### Legacy compatibility routing

Dependency blockers and a legacy integration table pointed users to cluster-specific compatibility configuration routes. These links bypassed the canonical provider registry and instance manage workspace.

### Prometheus instance context failure

The Prometheus Hero read `stats.capabilities`. A partial or deployment path that rendered the template without `stats` caused the complete instance page to fail. Capability metadata is now read from the mandatory `capability_summary` context.

## Implemented corrections

- Added a shared out-of-band operational feedback partial.
- Converted normal provider mutations to HTMX partial updates.
- Persisted one Activity Audit record for every action result.
- Added HTMX-aware deletion modal submission and `HX-Redirect` after successful instance deletion.
- Added shared uncovered operational-scope presentation for Prometheus and Alertmanager.
- Positioned uncovered scopes above the connection registry.
- Aligned Prometheus registry filters with the Alertmanager pattern: Search, Readiness, Compatibility.
- Aligned Prometheus pagination typography, URL state, controls, and empty action with the Alertmanager registry.
- Removed Environment as a Prometheus registry filter; environment remains provider metadata, not the primary connection lookup dimension.
- Repointed normal dependency actions to canonical registration and provider pages.
- Reduced the Prometheus legacy edit, registry, and cluster-configuration routes to redirect-only migration boundaries.
- Replaced the Hero dependency on `stats.capabilities` with `capability_summary.observed`.

## Final placement contract

Provider landing page order:

1. Hero.
2. Integration overview.
3. Uncovered operational scopes, only when present.
4. Connection registry.

Uncovered scope blocks are not part of the registry HTMX target. Registry filtering therefore never hides operational coverage gaps.

## Regression contract

Automated guardrails verify:

- No Prometheus instance Hero depends on `stats`.
- Normal provider templates do not link to legacy cluster compatibility pages.
- Same-page mutation forms use HTMX and stable targets.
- Mutation responses include out-of-band toast feedback.
- Prometheus and Alertmanager expose uncovered scope blocks before their registries.
- Prometheus registry uses Search, Readiness, and Compatibility.
- Prometheus pagination uses the same compact typography and URL behavior as Alertmanager.
- Provider route handlers record Activity Audit events for success, rejection, and failure outcomes across create, update, connection test, validation, runtime, binding, and delete actions.
- Alertmanager HTMX responses use the shared `operation_feedback` payload rather than provider-local feedback variable conventions.
