# Legacy Cutover Phase 2

Phase 2 moves the active Alertmanager binding path and Kubernetes connection reads to the canonical integration runtime foundation.

## Runtime authority

```text
Infrastructure asset
  -> IntegrationBinding
  -> IntegrationInstance
  -> provider record
  -> runtime adapter
```

Alertmanager asset mappings are read and written only through `integration_bindings`. Provider-specific `alertmanager_bindings` and cluster-scoped `alertmanager_configs` remain in the database solely for the later destructive cleanup migration; they are not active authorities.

Kubernetes credentials are read only through `KubernetesConnection`. New cluster creation no longer writes kubeconfig into the legacy `clusters.kubeconfig` column. The column is temporarily nullable until the destructive cleanup phase drops it.

## Compatibility routes

Cluster-centric Alertmanager URLs remain as redirects. They resolve a canonical binding and redirect to the standalone instance page; they no longer materialize legacy configuration records.

## Blocking boundary

Missing provider bindings affect only the selected asset and the features requiring that provider. Inventory requires the Kubernetes connection; metric analytics requires a mapped Prometheus instance; Alertmanager-specific features require a mapped Alertmanager instance.
