# Integration compatibility and readiness

KAORI treats reachability, product identity, runtime version, API compatibility, query compatibility, and feature readiness as separate states. Helm chart versions and chart `appVersion` values are deployment metadata; they do not replace runtime discovery.

## Validation lifecycle

1. Save configuration and set `validation_required`.
2. Validate network, TLS, and authentication.
3. Detect the responding product and runtime version.
4. Match a version-controlled compatibility profile.
5. Validate required APIs and capabilities.
6. Validate the provider-neutral API/core runtime profile.
7. Resolve an asset-scoped consumer profile for each binding.
8. Validate consumer metrics, labels, PromQL contracts, and retention where applicable.
9. Persist provider evidence on the provider and consumer evidence on the binding.
10. Allow each KAORI consumer only when its required binding capability is ready.

## Compatibility matrix

| Product | Supplied/runtime version | Deployment metadata | KAORI profile | Initial behavior |
|---|---:|---|---|---|
| Kubernetes | `1.20.15` | Per-cluster | `kubernetes-legacy-v1` | Degraded; feature/API validation required. |
| Kubernetes | `1.26.11` | Per-cluster | `kubernetes-standard-v1` | Supported, subject to API and RBAC probes. |
| Kubernetes | `1.29.4`, `1.29.5` | Per-cluster | `kubernetes-standard-v1` | Supported, subject to API and RBAC probes. |
| Prometheus | Runtime still must be detected | `kube-prometheus-stack-87.10.1`, chart app `v0.92.1` | `prometheus-http-api-v1` when runtime is `>=2,<3` | Block until `/api/v1/status/buildinfo` confirms the server version. |
| Thanos | `0.39.2` application family | Helm chart `17.3.1` | `thanos-query-prometheus-api-v1` | Supported initial query-backend profile after API and history probes. |
| Alertmanager | `0.25.0`, `0.33.1` | Per-cluster | `alertmanager-api-v2` | Supported after status, alerts, and silences probes. |
| MinIO | `RELEASE.2024-08-03T04-33-23Z` | Object-storage provider | `minio-release-2024-08-03` | Supported after MinIO S3 API identity, bucket discovery, and asset-scoped Prometheus metrics validation. |

The previous classification of `0.39.2` as a Prometheus version was incorrect. It belongs to the Thanos chart application version.

## Prometheus and Thanos topology

For Kubernetes assets, every cluster currently owns its own Prometheus and Alertmanager. Thanos provides long-retention query capability. KAORI must preserve these identities independently:

- Prometheus runtime/version and local-query readiness;
- Alertmanager runtime/version and API readiness;
- Thanos runtime/version and long-range query readiness;
- Helm chart name/version as deployment evidence only.

A general Prometheus instance may serve Kubernetes, MinIO, and future consumers simultaneously. Integration bindings therefore remain asset-aware and own consumer-specific metric evidence instead of hard-coding the Prometheus provider to one cluster or exporter family.

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
- `/integrations/storage` — Storage domain portfolio.
- `/integrations/minio/` — MinIO Object Storage provider inventory and registration.
- `/prometheus/instances/<instance_id>` — Prometheus manage workspace and operations.
- `/alertmanager/instances/<instance_id>` — Alertmanager manage workspace and operations.

Retired settings, provider registry, cluster-configuration, and edit URLs are not registered. Bookmarks must be updated to the canonical routes; KAORI does not keep an internal redirect layer.

## Safe presentation boundary

Integration list pages never render passwords, bearer tokens, embedded URL credentials, query strings, or fragments. Only scheme, hostname, optional port, and endpoint path are displayed. Validation messages must describe failed capability or compatibility checks without echoing credentials or raw response bodies.

## Supported compatibility profiles

- Kubernetes: `1.20–1.23` legacy, `1.24–1.29` standard, `1.30–1.33` modern, and `1.34–1.36` current.
- Prometheus: `2.40–2.x` legacy-supported and `3.x` current.
- Alertmanager: `0.25–0.26` legacy API-v2 and `0.27–0.33` current API-v2.
- MinIO: `RELEASE.2024-08-03T04-33-23Z` under the initial strict `minio-release-2024-08-03` profile.
- Thanos Query: `0.39`, `0.40`, and `0.41` profiles.

A matching version profile does not itself make an integration ready. Provider-level API/core checks must pass, while exporter/domain metrics, labels, and query contracts are evaluated independently on each asset binding.


## Route ownership

KAORI exposes one canonical management route per integration domain:

- `/integrations/kubernetes`
- `/integrations/prometheus`
- `/integrations/alertmanager`
- `/integrations/storage`
- `/integrations/minio/`

Provider blueprints may expose domain detail and operation endpoints, but KAORI does
not register legacy compatibility blueprints or active shim routes. Development
bookmarks are intentionally not retained when a canonical route replaces them.

## Direct Prometheus and intermediary endpoints

A direct Prometheus endpoint uses automatic runtime discovery. A Prometheus-compatible intermediary, including Thanos Query, must use manual compatibility selection because its build endpoint identifies the intermediary rather than the source Prometheus servers. Manual mode stores a supported endpoint/source compatibility profile and remains fail-closed until the provider-neutral core API contract passes. Asset-specific metrics, label schemas, PromQL contracts, and retention requirements are validated through consumer bindings.

### Interactive Prometheus validation boundary

Prometheus connection testing is intentionally split from full readiness validation. `Test Connection` is a short endpoint/API/profile check suitable for synchronous HTMX feedback. Provider `Run Full Validation` owns endpoint compatibility and the `prometheus-core-v1` contract (instant query, range query, series discovery, and label discovery). Kubernetes, MinIO, and future exporter/domain contracts are validated by each `IntegrationBinding`; the generic validation worker refreshes those bindings after provider validation.

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

Prometheus is a general metrics provider. Provider compatibility is independent of Kubernetes, MinIO, or any other exporter family.

Automatic mode contacts a direct Prometheus endpoint. `detected_version` and `compatibility_profile` therefore represent Prometheus. Provider `query_profile` resolves to the consumer-neutral `prometheus-core-v1` contract.

Manual mode contacts Thanos Query. `detected_version` and `compatibility_profile` therefore represent Thanos, while `source_prometheus_major` records the administrator-selected Prometheus source-major compatibility contract. The Thanos endpoint version must never be treated as a Prometheus runtime version.

Consumer metric contracts are binding-scoped. `kubernetes_cluster` bindings use `kubernetes-metrics-v1`; `object_storage_system` bindings use `minio-metrics-2024-v1`. A missing Kubernetes metric can degrade the Kubernetes binding without degrading a healthy general Prometheus provider or an unrelated MinIO binding.

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
| `query_profile` | `prometheus-core-v1` | `prometheus-core-v1` |
| `readiness_status` | Provider core-runtime readiness | Provider core-runtime readiness |

Configuration changes invalidate provider compatibility evidence and all dependent binding evidence. Existing Prometheus records should be revalidated after this split so provider readiness is rebuilt from `prometheus-core-v1` and each asset binding receives its canonical consumer profile/evidence.

## Kubernetes live API adapters

`kubernetes-api-v1` is the shared KAORI API contract. Runtime minor versions are recorded as lifecycle posture, while actual feature readiness comes from live discovery and authorization evidence. Inventory sync uses stable APIs first and only selects an explicitly implemented legacy adapter when discovery proves that the stable API is unavailable. Ingress and CronJob currently have tested legacy candidates. Core `v1` resources, including Secret and ConfigMap, do not use beta fallbacks; authorization failures are reported as feature capability gaps rather than version incompatibility.
