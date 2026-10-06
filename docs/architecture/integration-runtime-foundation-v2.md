# Integration Runtime Foundation v2

KAORI models managed assets and external runtimes as independent identities connected through provider-neutral `IntegrationBinding` records.

Metrics are represented by one global runtime category: **Metrics Source**. Product implementations are selected using `provider_key`; backend protocol/query behavior is selected using `adapter_key` and `query_language`.

## Canonical runtime identities

- Kubernetes connection: managed Kubernetes API/runtime identity.
- `MetricsSource`: reusable metrics query source with provider-neutral connection state.
- Alertmanager instance: reusable alert source/runtime identity.
- Object Storage system/provider: managed storage asset/API authority.

A Metrics Source can be reused by multiple Kubernetes or Object Storage assets. Consumer-specific metric evidence belongs to the binding, not to the provider record.

## Metrics Source contract

```text
provider_type = metrics_source
provider_key  = prometheus | thanos | future provider
adapter_key   = prometheus_http | future adapter
query_language = promql | future language
```

Prometheus/Thanos names are implementation metadata only. Analytics, Reports, Intelligence, Notifications, Kubernetes, Object Storage, jobs, runtime history, and routing consume the `metrics_source` category.

## Dependency resolution

Analytics resolves dependencies for the selected managed asset. A missing Metrics Source or Alertmanager binding blocks only the capability requiring that source. Inventory remains authoritative from committed Kubernetes/Object Storage inventory and does not infer provider ownership from metrics.

## Lifecycle rules

1. Register provider-neutral runtime identity.
2. Validate provider/adapter compatibility.
3. Create explicit asset binding.
4. Validate binding-specific evidence.
5. Persist runtime/binding evidence independently.
6. Delete bindings with the owning asset without deleting reusable shared sources.

Do not write asset-scoped provider configuration back into the asset record. Do not introduce product-specific metrics categories or compatibility wrappers.
