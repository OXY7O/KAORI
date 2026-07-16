# Prometheus Integration

Prometheus in KAORI is split into two contracts:

1. Endpoint compatibility
   - `prometheus-http-v2`
   - `prometheus-http-v3`
   - `thanos-query-v0-39`, `thanos-query-v0-40`, `thanos-query-v0-41`
2. Query/data compatibility
   - `promql-kubernetes-v1`

Automatic mode contacts Prometheus directly and detects the source major. Manual mode contacts Thanos Query, stores the Thanos endpoint identity, and requires an administrator-selected Prometheus source major (`2` or `3`).

`promql-kubernetes-v1` is the KAORI Kubernetes analytics query contract. It is independent from the Prometheus runtime major and is incremented only when metric, label, query, or result semantics change incompatibly.

Connection Test is intentionally fast. Full Validation performs metric discovery, label-schema checks, PromQL profile auditing, and retention probes. Runtime consumers must reject `blocked` and `validation_required` integrations.
