# Integration Runtime and Asset Mapping

KAORI treats Kubernetes, Prometheus-compatible metrics endpoints, and Alertmanager as independent runtimes. Asset relationships are explicit bindings; configuration ownership is never inferred from a template or from a global integration state.

## Runtime boundaries

- Kubernetes runtime: one registered API endpoint represented by a cluster record and observed through `KubernetesRuntimeAdapter`.
- Prometheus runtime: one standalone `PrometheusInstance`, reusable through `PrometheusBinding` records.
- Alertmanager runtime: one standalone `AlertmanagerInstance`, reusable through `AlertmanagerBinding` records.

Bindings use `scope_type=kubernetes_cluster` and `scope_key=<cluster UUID>` for Kubernetes Analytics.

## Analytics dependency policy

Dependency evaluation is selected-cluster scoped and feature scoped. A missing or degraded runtime for cluster B must never block cluster A. When no cluster is supplied, KAORI deterministically selects the first registered cluster (`created_at`, then UUID), not the first alphabetical name.

Metric pages require Kubernetes and Prometheus. Alert-specific pages additionally require Alertmanager. Inventory requires only the Kubernetes runtime and stored inventory snapshots.

## Presentation boundary

Templates consume display-ready values. Date/time conversion, unit conversion, percentages, status labels, and action URLs belong in services or presentation builders. Jinja templates must not construct provider routes or convert datetimes. Existing template-side formatting is migration debt and must be removed whenever the template is touched.
