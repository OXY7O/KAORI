# Prometheus and Thanos query integration

Prometheus is managed under the top-level Integrations domain. For the current Kubernetes topology, each cluster has one local Prometheus and Alertmanager, while Thanos supplies long-retention query capability. The future Server topology may use shared centralized instances, so code must use integration bindings rather than assume one endpoint per asset forever.

Runtime Prometheus version is detected from `/api/v1/status/buildinfo`. The kube-prometheus-stack chart version and chart app version are stored only as deployment metadata and must never be evaluated as the Prometheus binary version.

All PromQL is owned by `app/prometheus/query_profiles`. Legacy domain `queries.py` modules are compatibility exports only. See `docs/PROMQL_QUERY_PROFILES.md` for metadata, validation, retention, deprecation, and replacement rules.

`PromQLProfileAuditor` checks metric availability, label schema, optional execution of all registered queries, and historical coverage at 24h, 7d, 30d, and 60d. Prometheus engine compatibility and query readiness are persisted separately.

Thanos `0.39.2` is evaluated with `thanos-query-prometheus-api-v1`; it is not a Prometheus version. The endpoint used for historical validation must be the actual Thanos Query or Query Frontend endpoint when long retention is expected.
