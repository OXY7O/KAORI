# Integration Compatibility and Readiness

KAORI treats **integration category**, **provider identity**, **transport/query adapter**, **query language**, **runtime compatibility**, and **consumer binding readiness** as independent contracts. A product name must never become the global source category.

For metrics, the canonical category is always `metrics_source`.

```text
Integration category  metrics_source
        ↓
Provider key          prometheus | thanos | future provider
        ↓
Adapter key           prometheus_http | future adapter
        ↓
Query language        promql | future language
        ↓
Provider validation
        ↓
Asset binding validation
        ↓
Consumer eligibility
```

Prometheus and Thanos Query are current **provider implementations** of Metrics Source. They are not separate global integration categories and consumer domains must not branch on those product names.

## Validation lifecycle

1. Register the source under the canonical integration category.
2. Resolve `provider_key` from the Metrics Source provider catalog.
3. Resolve `adapter_key`, `query_language`, default routing horizon, and compatibility policy from that provider definition.
4. Validate network, TLS, authentication, endpoint identity, and adapter-level operations.
5. Automatically match the detected runtime version to the source-controlled qualification band and general contract.
6. Persist provider-level readiness evidence on the Metrics Source record.
7. Create an asset-scoped `IntegrationBinding`.
8. Resolve the binding profile by `adapter_key + asset_type`.
9. Validate consumer-specific signals, selectors, retention, and semantic capabilities.
10. Allow the consumer only when both provider readiness and the required binding capabilities are eligible.

Provider readiness and binding readiness are independent. A missing Kubernetes metric may degrade one Kubernetes binding without degrading a healthy Metrics Source or an unrelated Object Storage binding.

## Metrics Source provider model

The source record is provider-neutral. The canonical persisted identity is:

| Field | Meaning |
|---|---|
| `IntegrationInstance.provider_type` | Always `metrics_source` for metrics connections. |
| `MetricsSource.provider_key` | Concrete implementation, for example `prometheus` or `thanos`. |
| `MetricsSource.adapter_key` | Backend protocol adapter selected by the provider definition. |
| `MetricsSource.query_language` | Query language declared by the provider definition. |
| `MetricsSource.detected_version` | Version of the endpoint actually contacted by KAORI. |
| `MetricsSource.compatibility_profile` | Qualified endpoint/provider compatibility evidence. |
| `MetricsSource.compatibility_profile_override` | Exceptional persisted override for migration/diagnostic recovery only; normal operator flow uses automatic detected-version selection. |

The global resolver, runtime history, jobs, notifications, routing, analytics, reports, Intelligence, Kubernetes, and Object Storage use `metrics_source`. Product identity is presentation/adapter metadata and must not leak into the category contract.

## Current provider implementations

The active provider catalog is `app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml`.

- **Prometheus** — `provider_key=prometheus`, currently uses `adapter_key=prometheus_http`, `query_language=promql`, and prefers the recent-query horizon.
- **Thanos Query** — `provider_key=thanos`, currently uses the same Prometheus HTTP/PromQL adapter but has its own endpoint identity, compatibility profiles, and historical-query preference.

Sharing an adapter does not merge provider identities. A Thanos endpoint remains Thanos evidence; its version is never persisted as a Prometheus runtime version.

## Adding another metrics provider

A provider that implements an existing registered adapter/query contract should normally require only:

1. a new provider entry in the Metrics Source catalog;
2. compatibility metadata for that provider; and
3. tests proving provider registration/readiness behavior.

No DB table, global route, IntegrationBinding schema, analytics source key, report source key, runtime provider type, or consumer domain branch should change.

A provider using a new API or query language additionally requires a new backend adapter and the relevant binding-validation/query profiles. It still must not require a new global source category or changes to unrelated consumers.

## Adapter boundary

Backend-specific code lives under `app/integrations/observability/metrics_source/` and is selected by `adapter_key`.

The generic Metrics Source contract exposes operations such as:

- `connection.test`;
- `runtime.health`;
- `runtime.validate`;
- `query.session.build`;
- `validation.session.build`;
- `binding.validate`.

Consumers do not instantiate a Prometheus client or any provider-specific client directly. Query consumers operate through a generic Metrics Query Session. Validator implementations may use adapter-specific sessions behind the registry boundary.

## Query and binding boundary

Provider compatibility proves that the configured endpoint can satisfy the selected adapter contract. It does **not** prove that every downstream asset has the required metrics.

Binding profiles are selected by `adapter_key + asset_type` and own the consumer evidence. Current examples include:

```text
Metrics Source
  ├── Kubernetes binding      → kubernetes-metrics-v1
  └── Object Storage binding  → object-storage-metrics-v1
```

A future adapter can register different binding profiles without changing `IntegrationBinding` or the global consumer source category.

## Routing and horizons

Metrics routing is source-neutral. Eligible bindings may express:

- source role (`primary`, `secondary`, `fallback`);
- priority;
- query horizon (`recent`, `historical`, `balanced`); and
- routing weight.

The resolver selects an eligible/healthy Metrics Source and then evaluates horizon match and routing policy. Product names are not routing branches.

This permits a common pattern such as:

```text
recent      → Prometheus
historical  → Thanos Query
```

without making either product the global metrics abstraction.

## Compatibility authority layers

KAORI compatibility is intentionally split into five independent authorities:

1. **Annual lifecycle policy** — yearly KAORI support governance with a five-year calendar lookback.
2. **General contract profile** — a stable API/protocol/capability generation such as `kubernetes-core-v1`, `prometheus-http-core-v1`, `alertmanager-api-v2-contract-v1`, or `s3-object-storage-v1`.
3. **Version qualification mapping** — concrete upstream versions mapped to the general contract with Current or Extended KAORI support posture.
4. **Upstream lifecycle** — current, maintained, legacy, EOL, or archived upstream status; this is independent evidence.
5. **Observed runtime evidence** — actual API probes, RBAC, query behavior, S3 operations, payload metadata, and binding-specific consumer evidence.

### Annual policy governance

The first annual generation is `kaori-compatibility-policy-v1` for 2026.

```text
policy_year = 2026
lookback_years = 5
anchor_year = 2021
```

For each product, the lower-bound candidate is the latest stable release in the anchor year. The upper-bound candidate is the latest stable release already available at the annual policy snapshot. This makes annual rollover deterministic instead of selecting arbitrary historical versions.

Annual policy version and general core contract version are independent:

- `compatibility-policy-v1` becomes `v2` on the 2027 annual lifecycle refresh;
- `kubernetes-core-v1`, `prometheus-http-core-v1`, and other `core-vN` identities remain unchanged until their API/capability semantics require a breaking contract generation.

### Definition-driven automatic selection

Compatibility ranges are data. Runtime logic must not hard-code product release branches.

For semver providers, `app/definitions/catalogs/integrations/compatibility.yaml` declares the automatic version source, qualification floor/ceiling, version bands, band-to-`core-vN` mapping, support posture, and capability deltas. KAORI detects the provider version first and selects the matching band without asking the operator to choose a year, release family, or compatibility profile.

This is also how API evolution is modeled. If a future product range requires a new API generation, that version band maps to a new general core contract in the definition. The evaluator continues to execute the same generic resolution algorithm.

MinIO uses its Object Storage provider definition because its release identifier is date-based rather than semver, but it follows the same automatic range-matching principle.

### Lifecycle states

- **Current** — inside the annual window and current upstream-qualified line; live evidence may make the integration Ready.
- **Extended** — inside the KAORI five-year window but outside the current upstream line; supported with Degraded posture and upgrade guidance.
- **End of Life** — older than the annual policy floor; blocked.
- **Future Unverified** — newer than the annual upper bound; Degraded when all mandatory core probes still pass, but never automatically qualified.
- **Capability Mismatch** — mandatory live capability is missing; blocked regardless of version.

A matching qualification never makes an integration Ready by itself. Live provider validation and required consumer binding evidence remain authoritative.

## Alertmanager and Object Storage boundaries

Alertmanager remains the alert-provider category. MinIO remains an Object Storage provider. Their relationships to Metrics Source are explicit asset bindings, not embedded product ownership. Consumer alert contracts are binding-scoped.

For Object Storage, the authority boundary is:

```text
Object Storage provider  → storage/API authority
Metrics Source           → metric evidence authority
Alertmanager              → alert evidence authority
KAORI                     → registration, binding, validation, routing, correlation
```

Deleting an asset owner removes its asset bindings; reusable source instances remain independent unless explicitly deleted through their own governed lifecycle.


## Qualified compatibility baseline

Policy v1 / 2026 uses anchor year 2021 and a five-year annual lookback.

| Integration | General contract | Policy v1 qualified versions | Current / recommended baseline | Readiness authority |
|---|---|---|---|---|
| Kubernetes | `kubernetes-core-v1` | v1.23–v1.37 | v1.37.x; upstream-supported minors v1.35–v1.37 | live API discovery and feature-level RBAC |
| Prometheus | `prometheus-http-core-v1` | v2.32–v3.13.x | v3.13.3 LTS | provider-neutral Prometheus HTTP API probes plus asset binding evidence |
| Alertmanager | `alertmanager-api-v2-contract-v1` | v0.23–v0.34.x | v0.34.1 | API v2 status/alerts/silences probes plus binding-scoped alert evidence |
| Thanos Query | `prometheus-http-core-v1` | v0.24–v0.42.x | v0.42.4 | shared Prometheus HTTP API probes plus provider identity and asset binding evidence |
| MinIO | `s3-object-storage-v1` | `RELEASE.2021-12-29T06-49-06Z` through `RELEASE.2025-10-15T17-29-55Z` | latest retained community release; upstream archived | S3 reachability and bucket-discovery capability; release qualification is supporting evidence |

For Kubernetes specifically, v1.23 is the final stable minor released in 2021, while v1.37 is the latest stable minor at the 2026 policy snapshot. Upstream currently maintains only v1.35–v1.37, so v1.23–v1.34 are KAORI Extended rather than Current.

During the 2027 annual refresh, the policy generation becomes `kaori-compatibility-policy-v2`, the anchor year becomes 2022, and each product floor is recalculated from the latest stable release in 2022. The annual change is performed in definitions and evidence tests. General `core-vN` contracts do not change unless their capability semantics change, and even a new core generation is selected through definition mapping rather than product-version branching in evaluator code.

## Canonical navigation and route ownership

- `/integrations/` — integration overview.
- `/integrations/observability/metrics-sources` — Metrics Source inventory.
- `/integrations/observability/metrics-sources/new` — provider selector.
- `/integrations/observability/metrics-sources/<provider_key>/new` — generic provider registration.
- `/integrations/metrics-sources/instances/<instance_id>` — Metrics Source detail/operations.
- `/integrations/alertmanager` — Alertmanager inventory.
- `/integrations/storage` — Storage portfolio.
- `/integrations/minio/` — MinIO provider inventory/registration.

There are no product-specific Metrics Source route aliases or compatibility redirects. Retired bookmarks must be updated to canonical routes.

## Runtime identity and history

Runtime observations use `provider='metrics_source'`. Product identity is recorded in source metadata/evidence rather than creating product-specific runtime namespaces. The same rule applies to canonical JobExecution provider types and operational event namespaces.

## Safe presentation boundary

Integration pages never render passwords, bearer tokens, embedded URL credentials, query strings, or fragments. Only sanitized endpoint context and presentation-ready validation evidence are exposed.

UI wording should use **Metrics Source** whenever the concept is the category, dependency, routing source, lifecycle source, or integration ownership boundary. Product labels such as **Prometheus** or **Thanos Query** are shown only when identifying the selected provider implementation.

## Migration boundary

The hard cut to Metrics Source is performed by the Alembic revision `20260817_metrics_source_v2`. It renames the legacy metrics table/columns and rewrites canonical provider/runtime/job/event metadata into the `metrics_source` namespace.

Legacy names are permitted only inside migration upgrade/downgrade logic that transforms historical schema/data. Active runtime code must not implement dual-read, alias, fallback, redirect, or wrapper behavior for the retired namespace.
