# Integration Compatibility

KAORI separates compatibility by consumer boundary. Runtime versions from one product must never be reused as compatibility evidence for another product.

## Profile naming

Profiles use short, stable identifiers:

- Endpoint/API profile: `<product>-<api-family>-<runtime-major-or-line>`
- Data/query profile: `<query-language>-<asset-domain>-<contract-version>`
- Capability profile: `<capability-domain>-<contract-version>`

The final `v1` is the KAORI contract version. It changes only when the required API, metrics, labels, query semantics, or capability contract changes incompatibly.

## Kubernetes

Kubernetes compatibility protects Kubernetes API consumers: Inventory, Operations, and Governance.

- API profile: `kubernetes-api-v1`
- Runtime version: stored separately, for example `1.20.15` or `1.29.5`
- Lifecycle: `current`, `legacy`, or `unknown`
- Feature readiness: determined from live API discovery and RBAC

The API profile is intentionally broad and maintainable. KAORI does not create a profile for every Kubernetes minor release. Minor-version lifecycle warnings and removed/deprecated API checks remain separate from the API contract.

Current lifecycle window in code:

- `1.34 <= version < 1.37`: current
- `1.20 <= version < 1.34`: legacy
- other versions: unknown or unsupported until the matrix is updated

## Prometheus and Thanos

Prometheus compatibility protects PromQL consumers: Kubernetes Analytics, live dashboard metrics, Prometheus-backed reports, and Intelligence.

### Direct Prometheus

- Endpoint profiles: `prometheus-http-v2`, `prometheus-http-v3`
- Query profile: `promql-kubernetes-v1`
- Source major: detected automatically from `/api/v1/status/buildinfo`

### Thanos Query intermediary

- Endpoint profiles: `thanos-query-v0-39`, `thanos-query-v0-40`, `thanos-query-v0-41`
- Prometheus source major: selected manually as `2` or `3`
- Query profile: `promql-kubernetes-v1`

Thanos runtime version is endpoint evidence only. It must never be presented as the Prometheus source version. The manual source-major selection chooses the PromQL compatibility contract; full validation still checks required metrics, labels, queries, and retention.

Future domains can reuse the endpoint profiles with different query profiles:

- `promql-server-v1`
- `promql-hci-v1`

Readiness is calculated per endpoint and per query/data profile, not only per Prometheus instance.

## Alertmanager

Alertmanager compatibility protects Alerts & Anomalies, Alert Intelligence, silence workflows, and routing posture.

- Endpoint profiles: `alertmanager-api-v2-legacy`, `alertmanager-api-v2-current`
- Capability profile: `alert-management-v1`
- Detection: automatic through the direct Alertmanager endpoint
- API policy: API v2 only; no API v1 fallback

The endpoint profile answers whether the runtime/API line is supported. The capability profile defines the alert, silence, status, and routing checks required by KAORI.

## Validation lifecycle

1. Save configuration.
2. Mark the integration `validation_required`.
3. Test connectivity and runtime identity.
4. Match the endpoint/API profile.
5. Validate capability or data/query profile.
6. Calculate feature readiness.
7. Store validation evidence and timestamp.

Unknown or unsupported endpoint versions fail closed. Missing optional capability may degrade only the affected feature; missing required capability blocks that consumer.
