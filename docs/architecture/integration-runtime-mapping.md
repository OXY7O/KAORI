# Integration Runtime Mapping

KAORI treats Kubernetes, Metrics Source, Alertmanager, and Object Storage identities independently. Relationships are explicit `IntegrationBinding` records; configuration ownership is never inferred from templates or global state.

- Kubernetes runtime: canonical Kubernetes connection owned by the cluster.
- Metrics runtime: one standalone `MetricsSource`, reusable through canonical `IntegrationBinding` records.
- Alert runtime: one standalone Alertmanager instance, reusable through canonical bindings.
- Object Storage runtime: provider-owned managed storage identity with observability sources attached through bindings.

Metrics consumers resolve `provider_type='metrics_source'`. They may display the concrete `provider_key` label, but they must not branch on Prometheus, Thanos, or another product to locate the source.

Metric pages require an eligible Metrics Source binding for the selected asset. Alert-specific pages resolve Alertmanager first where that domain contract requires it and may use Metrics Source alert-state evidence only through the generic metrics adapter capability. Inventory does not require a metrics product.
