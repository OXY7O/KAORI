# Alertmanager integration

Alertmanager compatibility protects Kubernetes Analytics alert consumers, Alert Intelligence, silence operations, and routing posture. Alertmanager is managed under the top-level **Integrations** domain and remains bound one-to-one to a Kubernetes cluster for the current Kubernetes architecture. The data model must remain extensible for a future centralized Server alerting service.

Validation detects the version through `/api/v2/status` and probes `/api/v2/alerts` and `/api/v2/silences`. The initial profile is `alertmanager-api-v2`. KAORI must not use or fall back to API v1.

Configuration changes invalidate compatibility evidence. A reachable endpoint is blocked when version matching or a required API capability fails.

## Navigation and API profiles

The canonical inventory route is `/integrations/alertmanager`; per-cluster configuration is `/integrations/alertmanager/cluster/<cluster_id>`. KAORI supports Alertmanager `0.25–0.26` as a legacy API-v2 profile and `0.27–0.33` as the current API-v2 profile. API v1 is never used as a fallback.
