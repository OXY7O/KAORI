# Alertmanager integration

Alertmanager is managed under the top-level **Integrations** domain and remains bound one-to-one to a Kubernetes cluster for the current Kubernetes architecture. The data model must remain extensible for a future centralized Server alerting service.

Validation detects the version through `/api/v2/status` and probes `/api/v2/alerts` and `/api/v2/silences`. The initial profile is `alertmanager-api-v2`. KAORI must not use or fall back to API v1.

Configuration changes invalidate compatibility evidence. A reachable endpoint is blocked when version matching or a required API capability fails.
