# Integration compatibility and readiness

KAORI treats reachability, product identity, runtime version, API compatibility, query compatibility, and feature readiness as separate states. Helm chart versions and chart `appVersion` values are deployment metadata; they do not replace runtime discovery.

## Validation lifecycle

1. Save configuration and set `validation_required`.
2. Validate network, TLS, and authentication.
3. Detect the responding product and runtime version.
4. Match a version-controlled compatibility profile.
5. Validate required APIs and capabilities.
6. Select the API or PromQL profile.
7. Validate metrics, labels, query execution, and retention where applicable.
8. Persist validation evidence.
9. Allow each KAORI consumer only when its required capability is ready.

## Compatibility matrix

| Product | Supplied/runtime version | Deployment metadata | KAORI profile | Initial behavior |
|---|---:|---|---|---|
| Kubernetes | `1.20.15` | Per-cluster | `kubernetes-legacy-v1` | Degraded; feature/API validation required. |
| Kubernetes | `1.26.11` | Per-cluster | `kubernetes-standard-v1` | Supported, subject to API and RBAC probes. |
| Kubernetes | `1.29.4`, `1.29.5` | Per-cluster | `kubernetes-standard-v1` | Supported, subject to API and RBAC probes. |
| Prometheus | Runtime still must be detected | `kube-prometheus-stack-87.10.1`, chart app `v0.92.1` | `prometheus-http-api-v1` when runtime is `>=2,<3` | Block until `/api/v1/status/buildinfo` confirms the server version. |
| Thanos | `0.39.2` application family | Helm chart `17.3.1` | `thanos-query-prometheus-api-v1` | Supported initial query-backend profile after API and history probes. |
| Alertmanager | `0.25.0`, `0.33.1` | Per-cluster | `alertmanager-api-v2` | Supported after status, alerts, and silences probes. |

The previous classification of `0.39.2` as a Prometheus version was incorrect. It belongs to the Thanos chart application version.

## Prometheus and Thanos topology

For Kubernetes assets, every cluster currently owns its own Prometheus and Alertmanager. Thanos provides long-retention query capability. KAORI must preserve these identities independently:

- Prometheus runtime/version and local-query readiness;
- Alertmanager runtime/version and API readiness;
- Thanos runtime/version and long-range query readiness;
- Helm chart name/version as deployment evidence only.

A future Server domain may bind multiple server assets to one centralized Prometheus and Alertmanager instance. Integration bindings must therefore remain asset-aware rather than hard-coded permanently to one cluster.

## Deprecation behavior

- Unknown or unsupported required API: blocked.
- Missing optional capability: degraded.
- Removed API with a registered replacement: replacement required.
- Removed API without direct replacement: feature blocked with remediation guidance.
- Deprecated PromQL definition: resolve its registered replacement key.
- Missing metric or label schema: only dependent capabilities are degraded or blocked.

The deprecation registry is `app/integrations/deprecations.py`. PromQL profile details are documented in `docs/PROMQL_QUERY_PROFILES.md`.
