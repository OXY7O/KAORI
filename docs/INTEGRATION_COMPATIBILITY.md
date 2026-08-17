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
5. Match a version-controlled compatibility profile where the selected adapter/provider requires one.
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
| `MetricsSource.compatibility_profile_override` | Explicit supported profile selection when automatic endpoint detection is insufficient. |

The global resolver, runtime history, jobs, notifications, routing, analytics, reports, Intelligence, Kubernetes, and Object Storage use `metrics_source`. Product identity is presentation/adapter metadata and must not leak into the category contract.

## Current provider implementations

The active provider catalog is `app/definitions/catalogs/integrations/metrics_source.yaml`.

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

Backend-specific code lives under `app/integrations/metrics/` and is selected by `adapter_key`.

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

## Compatibility profiles

Compatibility data remains product/adapter-specific because endpoint behavior is product-specific. Current examples include Prometheus HTTP profiles and Thanos Query profiles. This is expected and is not a category-level coupling.

A matching version profile alone does not make an integration Ready. Core adapter validation and required asset-binding evidence must also pass.

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
