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

Query deprecation and replacement metadata is owned by `app/integrations/prometheus/query_profiles/types.py` and each registered `QueryDefinition`. PromQL profile details are documented in `docs/PROMQL_QUERY_PROFILES.md`.

## Canonical navigation and route ownership

Integration inventory and configuration are owned by the top-level `Integrations` domain.

- `/integrations/` — cross-cluster integration overview.
- `/integrations/prometheus` — Prometheus inventory.
- `/integrations/alertmanager` — Alertmanager inventory.
- `/prometheus/instances/<instance_id>` — Prometheus manage workspace and operations.
- `/alertmanager/instances/<instance_id>` — Alertmanager manage workspace and operations.

Retired settings, provider registry, cluster-configuration, and edit URLs are not registered. Bookmarks must be updated to the canonical routes; KAORI does not keep an internal redirect layer.

## Safe presentation boundary

Integration list pages never render passwords, bearer tokens, embedded URL credentials, query strings, or fragments. Only scheme, hostname, optional port, and endpoint path are displayed. Validation messages must describe failed capability or compatibility checks without echoing credentials or raw response bodies.

## Supported compatibility profiles

- Kubernetes: `1.20–1.23` legacy, `1.24–1.29` standard, `1.30–1.33` modern, and `1.34–1.36` current.
- Prometheus: `2.40–2.x` legacy-supported and `3.x` current.
- Alertmanager: `0.25–0.26` legacy API-v2 and `0.27–0.33` current API-v2.
- Thanos Query: `0.39`, `0.40`, and `0.41` profiles.

A matching version profile does not itself make an integration ready. Required API endpoints, capabilities, metrics, labels, and query probes must also pass.


## Route ownership

KAORI exposes one canonical management route per integration domain:

- `/integrations/kubernetes`
- `/integrations/prometheus`
- `/integrations/alertmanager`

Provider blueprints may expose domain detail and operation endpoints, but KAORI does
not register legacy compatibility blueprints or active shim routes. Development
bookmarks are intentionally not retained when a canonical route replaces them.

## Direct Prometheus and intermediary endpoints

A direct Prometheus endpoint uses automatic runtime discovery. A Prometheus-compatible intermediary, including Thanos Query, must use manual compatibility selection because its build endpoint identifies the intermediary rather than the source Prometheus servers. Manual mode stores only a supported major compatibility profile and remains fail-closed until API, PromQL, metric, label-schema, and retention checks pass.

### Interactive Prometheus validation boundary

Prometheus connection testing is intentionally split from full readiness validation. `Test Connection` is a short endpoint/API/profile check suitable for synchronous HTMX feedback. `Run Full Validation` owns metric discovery, required-label checks, versioned PromQL audit, and retention probes. This separation prevents Thanos-backed endpoints from appearing stuck while a large `/api/v1/series` audit is running and makes the cost of the operation explicit to the administrator.

## Final compatibility-domain ownership

KAORI evaluates three independent compatibility domains. A successful check in one domain must not be reused as evidence for another.

### Kubernetes compatibility

Consumers: Kubernetes Inventory, Kubernetes Operations, and Kubernetes Governance.

Evidence:

- Kubernetes server version;
- discovered API groups and resources;
- required RBAC verbs;
- deprecated or removed APIs;
- readiness per feature.

### Prometheus compatibility

Consumers: Kubernetes Analytics, dashboard live metrics, Prometheus-backed reports, and Prometheus-backed intelligence.

Automatic mode contacts a direct Prometheus endpoint. `detected_version` and `compatibility_profile` therefore represent Prometheus.

Manual mode contacts Thanos Query. `detected_version` and `compatibility_profile` therefore represent Thanos, while `source_prometheus_major` represents the administrator-selected Prometheus major contract used to select the PromQL profile. The Thanos endpoint version must never be treated as a Prometheus runtime version.

Both modes require full validation of required metrics, label schemas, PromQL, and retention before Analytics readiness can become Ready.

### Alertmanager compatibility

Consumers: Alerts & Anomalies, Alert Intelligence, silence workflows, and routing posture.

Alertmanager is detected automatically from its direct endpoint and validated through API v2 capabilities. Alertmanager compatibility is not inferred from Prometheus, Thanos, or Kubernetes versions.

## Prometheus persisted identity

| Field | Direct Prometheus | Thanos Query mode |
|---|---|---|
| `endpoint_product` | `prometheus` | `thanos` |
| `detected_version` | Prometheus runtime | Thanos runtime |
| `compatibility_profile` | Prometheus endpoint profile | Thanos endpoint profile |
| `source_prometheus_major` | detected Prometheus profile | selected Prometheus 2.x/3.x source profile |
| `query_profile` | selected from detected source | selected from manual source profile |
| `readiness_status` | Kubernetes Analytics readiness | Kubernetes Analytics readiness |

Configuration changes invalidate all compatibility evidence. Existing manual-mode records created before this split must be revalidated because earlier builds could store a synthetic Prometheus major or a Thanos version in the same field.

## Kubernetes live API adapters

`kubernetes-api-v1` is the shared KAORI API contract. Runtime minor versions are recorded as lifecycle posture, while actual feature readiness comes from live discovery and authorization evidence. Inventory sync uses stable APIs first and only selects an explicitly implemented legacy adapter when discovery proves that the stable API is unavailable. Ingress and CronJob currently have tested legacy candidates. Core `v1` resources, including Secret and ConfigMap, do not use beta fallbacks; authorization failures are reported as feature capability gaps rather than version incompatibility.
