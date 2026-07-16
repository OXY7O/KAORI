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

## Canonical navigation and route ownership

Integration inventory and configuration are owned by the top-level `Integrations` domain.

- `/integrations/` — cross-cluster integration overview.
- `/integrations/prometheus` — Prometheus inventory.
- `/integrations/alertmanager` — Alertmanager inventory.
- `/integrations/prometheus/cluster/<cluster_id>` — Prometheus configuration and validation.
- `/integrations/alertmanager/cluster/<cluster_id>` — Alertmanager configuration and validation.

Legacy `/settings/prometheus`, `/settings/alertmanager`, `/prometheus/...`, and `/alertmanager/...` URLs redirect to canonical routes. Remove the redirect layer only after external bookmarks and activity records have aged out.

## Safe presentation boundary

Integration list pages never render passwords, bearer tokens, embedded URL credentials, query strings, or fragments. Only scheme, hostname, optional port, and endpoint path are displayed. Validation messages must describe failed capability or compatibility checks without echoing credentials or raw response bodies.

## Supported compatibility profiles

- Kubernetes: `1.20–1.23` legacy, `1.24–1.29` standard, `1.30–1.33` modern, and `1.34–1.36` current.
- Prometheus: `2.40–2.x` legacy-supported and `3.x` current.
- Alertmanager: `0.25–0.26` legacy API-v2 and `0.27–0.33` current API-v2.
- Thanos Query: `0.39`, `0.40`, and `0.41` profiles.

A matching version profile does not itself make an integration ready. Required API endpoints, capabilities, metrics, labels, and query probes must also pass.


## Route ownership and legacy compatibility

Canonical integration routes are owned by the integration-specific blueprints under
`/integrations/prometheus` and `/integrations/alertmanager`. The same blueprints are
registered once more with unique legacy registration names for `/prometheus` and
`/alertmanager`; this preserves old deep links without maintaining redirect-only
wrapper blueprints. Settings shortcuts use explicit `308` redirects to the canonical
integration list pages. New code and generated links must always use canonical
`integrations.*`, `prometheus.*`, and `alertmanager.*` endpoints.


## Direct Prometheus and intermediary endpoints

A direct Prometheus endpoint uses automatic runtime discovery. A Prometheus-compatible intermediary, including Thanos Query, must use manual compatibility selection because its build endpoint identifies the intermediary rather than the source Prometheus servers. Manual mode stores only a supported major compatibility profile and remains fail-closed until API, PromQL, metric, label-schema, and retention checks pass.

### Interactive Prometheus validation boundary

Prometheus connection testing is intentionally split from full readiness validation. `Test Connection` is a short endpoint/API/profile check suitable for synchronous HTMX feedback. `Run Full Validation` owns metric discovery, required-label checks, versioned PromQL audit, and retention probes. This separation prevents Thanos-backed endpoints from appearing stuck while a large `/api/v1/series` audit is running and makes the cost of the operation explicit to the administrator.
