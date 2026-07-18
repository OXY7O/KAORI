# Integration Runtime Foundation v2

## Decision

KAORI models Kubernetes, Prometheus-compatible endpoints, and Alertmanager as independent integration runtimes. Assets and runtimes are related only through provider-neutral bindings.

```text
Infrastructure asset
    -> IntegrationBinding
        -> IntegrationInstance
            -> provider connection record
            -> RuntimeAdapter
            -> RuntimeState / RuntimeObservation
```

## Canonical models

- `IntegrationInstance`: provider-neutral identity, lifecycle, readiness, and health.
- `IntegrationBinding`: maps a runtime to an asset, role, priority, and capability scope.
- `KubernetesConnection`: Kubernetes API credentials and compatibility state separated from `Cluster` asset metadata.
- `PrometheusInstance`: Prometheus/Thanos-specific connection and query-validation state.
- `AlertmanagerInstance`: Alertmanager-specific connection and capability state.

Provider binding tables remain readable only during the compatibility window. New consumers resolve through `app.integrations.resolver.resolve_integration()`.

## Asset-scoped dependency policy

Analytics resolves dependencies for the selected Kubernetes asset only. A missing Prometheus or Alertmanager mapping blocks only the selected asset and only the feature requiring that provider. Inventory depends on Kubernetes runtime and stored inventory; Prometheus and Alertmanager are optional enrichment sources.

## Runtime persistence

Runtime observations reference `integration_instance_id`. The legacy `provider + instance_id` fields remain temporarily for diagnostics and migration traceability.

## Presentation boundary

Templates receive display-ready datetime, unit, percentage, status, and action values. Raw numeric values may be supplied separately for charting. New Jinja templates must not call `strftime`, `astimezone`, or perform byte/unit conversion.

## Legacy removal sequence

1. Backfill canonical instances and bindings.
2. Switch all resolvers and scheduled runtime refresh to canonical instances.
3. Stop writing cluster-scoped Prometheus and Alertmanager configurations.
4. Move Kubernetes credentials from `Cluster` to `KubernetesConnection`.
5. Remove compatibility fallbacks after repository search and integration tests show no consumers.
6. Drop provider-specific binding and legacy configuration tables in a dedicated destructive migration.

The destructive schema cleanup is deliberately separated from the canonical cutover so production upgrades remain recoverable. Development environments may reset the database after the cutover migration.
