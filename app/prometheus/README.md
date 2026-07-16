# Prometheus and Thanos query integration

Prometheus is managed under the top-level Integrations domain. For the current Kubernetes topology, each cluster has one local Prometheus and Alertmanager, while Thanos supplies long-retention query capability. The future Server topology may use shared centralized instances, so code must use integration bindings rather than assume one endpoint per asset forever.

Runtime Prometheus version is detected from `/api/v1/status/buildinfo`. The kube-prometheus-stack chart version and chart app version are stored only as deployment metadata and must never be evaluated as the Prometheus binary version.

All PromQL is owned by `app/prometheus/query_profiles`. Legacy domain `queries.py` modules are compatibility exports only. See `docs/PROMQL_QUERY_PROFILES.md` for metadata, validation, retention, deprecation, and replacement rules.

`PromQLProfileAuditor` checks metric availability, label schema, optional execution of all registered queries, and historical coverage at 24h, 7d, 30d, and 60d. Prometheus engine compatibility and query readiness are persisted separately.

Thanos `0.39.2` is evaluated with `thanos-query-prometheus-api-v1`; it is not a Prometheus version. The endpoint used for historical validation must be the actual Thanos Query or Query Frontend endpoint when long retention is expected.

## Navigation and compatibility profiles

The canonical inventory route is `/integrations/prometheus`; per-cluster configuration is `/integrations/prometheus/cluster/<cluster_id>`. Runtime versions are normalized before matching: for example `prometheus/Prometheus/v3.13.0-distroless` becomes `3.13.0`, while the build variant remains metadata. Supported runtime profiles are Prometheus `2.40–2.x` and `3.x`; every saved configuration returns to `validation_required` until API, query profile, metric, and label checks pass.


## Runtime version detection modes

Prometheus integrations use one of two explicit compatibility modes:

- `automatic`: for a direct Prometheus endpoint. KAORI reads `/api/v1/status/buildinfo` and selects the matching versioned compatibility and PromQL profile.
- `manual`: for a Prometheus-compatible intermediary such as Thanos Query where build information describes the intermediary rather than the underlying Prometheus runtime. An administrator must select the supported Prometheus major profile (`2.x` or `3.x`). KAORI still validates API capability, required metrics, labels, query execution, and retention before runtime use.

Changing the detection mode or manual profile invalidates prior validation evidence and returns the integration to `validation_required`. Manual selection is never treated as proof of readiness by itself.
