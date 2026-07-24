# Legacy Cutover Phase 4 — Instance-Scoped Prometheus Operations

Prometheus runtime operations now use `PrometheusInstance` as the execution identity.

## Active flow

```text
PrometheusInstance
    -> PrometheusService(instance)
    -> PrometheusClient
    -> RuntimeAdapter
    -> Runtime History
```

Kubernetes cluster context remains optional and is only required by asset-specific analytics consumers. Endpoint connectivity, compatibility validation, capability discovery, and runtime-history persistence no longer require a cluster lookup.

## Compatibility boundary

Cluster-scoped routes remain temporarily available for existing bookmarks and consumers. The visible configuration actions now post to instance-scoped routes. A later destructive phase can remove the compatibility routes after repository-wide call-site verification.
