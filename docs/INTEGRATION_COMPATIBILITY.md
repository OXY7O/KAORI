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

## Kubernetes API lifecycle and fallback policy

`kubernetes-api-v1` is the KAORI API contract, not a promise that every Kubernetes minor exposes the same resource versions. Cluster validation must combine the runtime version with live API discovery and feature-level capability checks.

KAORI uses the stable API selected by each feature whenever it is served. A legacy adapter may be used only when all of the following are true:

- the stable resource version required by the primary adapter is not served;
- a documented legacy resource version is still served by the target cluster;
- KAORI has an explicit parser/adapter and test coverage for that legacy schema;
- the feature result is marked `compatible_with_warnings` or `degraded`; and
- the fallback does not weaken a security or mutation guardrail.

Fallback is selected from live discovery evidence, not from the lifecycle label alone. `legacy` is a warning and adapter hint; it is not an instruction to silently retry every request with a beta API.

Core resources such as `Secret`, `ConfigMap`, `Namespace`, `Pod`, and `Service` use `core/v1` across the currently supported KAORI cluster range. A Secret inventory failure therefore must be diagnosed as connectivity, RBAC, timeout, response-size, or collector behavior; it must not be treated as a missing beta/legacy Secret API. Version-aware adapters are primarily relevant to resources that moved between API groups or versions, such as Ingress, CronJob, and PodDisruptionBudget.

The expected feature evaluation is:

```text
Kubernetes runtime version
+ live API discovery
+ selected stable or explicit legacy adapter
+ RBAC verb validation
= feature readiness
```

A missing stable API with no tested legacy adapter blocks only the affected feature, not the whole cluster.

