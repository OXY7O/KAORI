# Prometheus Domain Boundary

`app/prometheus` owns KAORI's Prometheus registration workflow, instance
workspace, scope binding policy, source resolution, presentation, Activity
Audit integration, and HTTP routes.

The provider implementation is exclusively owned by
`app/integrations/prometheus/`. Transport, query profiles, capability
declarations, validation evidence, compatibility profiles, and the runtime
adapter must not be duplicated in this domain package.

Domain services call the Integration Registry for provider operations.
Persistence uses `PrometheusInstance`, `IntegrationInstance`, and
`IntegrationBinding` only. No alternate Python import path remains for retired provider packages, and no
bookmark redirects remain for replaced routes.

## Prometheus Manage UI and lifecycle contract

Prometheus and Prometheus-compatible query endpoints are registered as reusable provider instances. Each instance has one canonical manage workspace containing
Configuration, Validation & Capabilities, Runtime & History, and Scope &
Resolution. Provider-local configuration pages and cluster-scoped routes are not
part of the active contract.

### Instance deletion

Instance deletion is a governed database lifecycle action and has no live
Prometheus or Thanos dependency. Every provider-neutral scope binding must be removed first, including disabled bindings. Active provider jobs also block the
operation. KAORI repeats these checks in the service boundary before deleting
the provider record and its canonical integration identity atomically.

Historical runtime observations and Activity Audit records remain available.
The Delete Instance control is shown only in the contextual Scope & Resolution
workspace, adjacent to its binding and job blockers.
