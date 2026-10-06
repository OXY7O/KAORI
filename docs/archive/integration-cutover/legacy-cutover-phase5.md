# Legacy Cutover Phase 5

Phase 5 removes the last active legacy Prometheus consumer lookup and makes the standalone runtime detail page independent from Kubernetes bindings.

## Runtime boundary

Prometheus connection testing, compatibility validation, health state, and runtime history belong to the Prometheus instance. Kubernetes Analytics resolves that instance through a canonical `IntegrationBinding` and remains asset-scoped.

## Changes

- `PrometheusConsumer` resolves `PrometheusInstance` through `resolve_instance_for_cluster()`.
- Direct reads from `PrometheusConfig` are removed from the active consumer facade.
- `/integrations/prometheus/instances/<id>` works for both bound and unbound runtimes.
- Unbound runtimes can run connection tests, full validation, and view runtime history.
- Cluster-specific configuration remains available from each binding while compatibility routes are retained.

No database migration is required.
