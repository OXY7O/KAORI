# KAORI Integration Kernel

`app/integrations` is KAORI's provider-neutral integration kernel. It gives the
core a small, stable API while provider implementation remains isolated.

```text
Route → Domain Service → Integration Registry → Adapter → External System
```

## Integration taxonomy

Providers are registered under a stable domain and capability. Taxonomy is
registry metadata, not duplicated persistence on `IntegrationInstance`.

```text
Integrations
├── Orchestration
│   └── Cluster Orchestration
│       └── Kubernetes
├── Observability
│   ├── Metrics
│   │   └── Metrics Source
│   └── Alerting
│       └── Alertmanager
└── Storage
    ├── Object Storage
    │   └── MinIO
    ├── File Storage
    └── Block Storage
```

`worker_domain` remains execution metadata and must not be reused as the UI or
architecture taxonomy. `app/definitions/catalogs/integrations/taxonomy.yaml` is the canonical domain/capability map; `taxonomy.py` is its validated runtime adapter.

## Physical namespace contract

Folder layout follows the same hierarchy as the persisted integration identity:

```text
app/integrations/
├── orchestration/
│   └── container_orchestrator/
│       ├── frontpage.py
│       └── adapters/
│           └── kubernetes_api/
├── observability/
│   ├── metrics_source/
│   │   ├── adapters/
│   │   │   └── prometheus_http/
│   │   ├── binding_validators/
│   │   └── query_profiles/
│   └── alert_source/
│       └── providers/
│           └── alertmanager/
└── storage/
    ├── object_storage/
    │   ├── adapters/
    │   │   └── s3/
    │   └── providers/
    │       └── minio/
    ├── file_storage/
    └── block_storage/
```

The rules are deliberate:

- domain and integration-type directories are stable architecture names;
- a product name may appear only in a provider implementation or provider definition;
- a reusable protocol/API belongs under `adapters/<adapter_key>/`;
- providers that share an adapter reuse that adapter rather than copying transport code;
- provider-neutral routing, bindings, query profiles, and consumer contracts stay at the integration-type level;
- application workspaces mirror the same intent: `app/metrics_sources`, `app/alert_sources/providers/<provider>`, and `app/object_storage/providers/<provider>`;
- templates and definition catalogs mirror the same domain/integration-type/provider hierarchy.

For example, Prometheus and Thanos share `prometheus_http`; MinIO, Garage, and AWS S3 can share the `s3` adapter; Rancher and Sangfor Kubernetes Engine can reuse `kubernetes_api` after producing or resolving a Kubernetes API connection. Adding a provider must not create a new product directory directly under `app/integrations`.


## Navigation projection

The sidebar renders domain workspaces from the canonical taxonomy:

```text
Integrations
├── Overview
├── Orchestration
├── Observability
└── Storage
```

Product-specific pages remain provider workspaces beneath those domains. Each registered
`IntegrationModule` declares `navigation_endpoint_prefixes`, allowing deep routes such as
`cluster.*`, `metrics.*`, and `alertmanager.*` to retain the correct domain active state
without provider-name branching in the sidebar template.

## Binding model

Bindings remain asset-centric and provider-neutral:

```text
IntegrationInstance ── IntegrationBinding ── Managed Asset
                          asset_type
                          asset_key
```

A provider does not persist a direct foreign key to another provider. Multiple
providers may bind to the same asset and serve different capabilities. For
example:

```text
Kubernetes Cluster
├── Kubernetes API provider
├── Metrics Source
└── Alertmanager alerting provider

Object Storage System
├── MinIO API provider
├── Metrics Source
└── Alertmanager alerting provider
```

New domains must reuse `IntegrationBinding`; do not introduce pair-specific
binding tables such as `minio_metrics_bindings`.

## Rules

- Cross-domain callers resolve integrations with `get_integration()` or
  `execute_integration_operation()`.
- Provider-specific code lives under the matching `providers/<provider>/` namespace; reusable transport/API code lives under `adapters/<adapter_key>/`.
- Every provider registers `domain_key`, `capability_key`, catalog metadata,
  canonical-record reverse loading, workspace routing, queue ownership,
  capability keys, and compatibility profiles through `IntegrationModule`.
- UI/domain packages may contain forms, route handlers, presentation builders,
  and provider-specific business workflow, but they must not duplicate clients,
  adapters, credentials, bindings, or runtime persistence.
- Every asynchronous operation uses `JobExecution` and an explicitly mapped
  queue.
- SQLAlchemy models remain centralized under `app/models/`.
- Retired bookmark routes are removed; canonical integration URLs are the only supported entry points.

## Shared contracts

- `contracts/base.py`: runtime and operation adapter protocols.
- `contracts/capabilities.py`: capability declarations and evidence contract.
- `contracts/results.py`: provider-neutral runtime and operation results.
- `contracts/exceptions.py`: stable orchestration exceptions.
- `app/definitions/catalogs/integrations/`: versioned provider, compatibility, consumer-profile, and taxonomy definitions.
- `taxonomy.py`: validated runtime adapter for stable integration domains and capabilities.
- `registry.py`: registration, taxonomy ownership, lookup, dispatch, model
  loading, detail routing, failure hooks, and queue map.
- `binding_service.py`: provider-neutral source-to-asset binding entrypoint.

## Validation levels

KAORI separates provider validity from consumer eligibility. Provider readiness
must never depend on one downstream domain/exporter family.

```text
Provider
  → Compatibility Profile
  → Provider Capability Set
  → Core Validation
  → Provider Ready
  → Asset Binding
  → Consumer Profile
  → Binding Validation
  → Consumer Eligibility
```

1. **Test Connection** verifies submitted endpoint identity and reachability.
2. **Provider Core Validation** resolves the provider compatibility profile,
   validates provider-owned capabilities, and persists provider evidence through
   `integration-validation` workers. It is consumer-neutral.
3. **Binding Validation** proves that one ready provider can serve one managed
   asset. The asset binding selects a consumer profile, selector, and validation
   evidence without changing provider readiness.
4. **Consumer Eligibility** combines provider-core execution capability evidence with validated binding evidence for the asset. Transport/query capabilities remain provider-owned; metric/selector evidence remains consumer-binding-owned.
5. **Runtime Refresh** performs lightweight provider health observation using
   `integration-runtime` workers and does not replace Core or Binding Validation.

The full-validation worker dispatches through the registry and does not branch
on provider names. Providers with `binding.validate` automatically participate
in binding refresh. Provider-specific failure persistence is exposed through a
registered hook.

Compatibility profile and consumer profile are different contracts:

- **Compatibility profile** answers whether the detected product/version/API
  contract is supported by KAORI and which provider capabilities can be
  validated.
- **Consumer profile** answers what asset-specific evidence is required after a
  binding exists.

Metrics Source is the canonical metrics abstraction. `provider_key` records product
identity, `adapter_key` selects the backend implementation, and `query_language`
records the source query contract. `observability/metrics_source/binding_profiles.py` selects consumer
validation by `adapter_key + asset_type`: Kubernetes registers
`kubernetes-metrics-v1`; Object Storage registers the provider-neutral
`object-storage-metrics-v1`. Consumer validators may then resolve provider-qualified
evidence contracts such as MinIO Metrics v2 without leaking backend products into
the generic binding registry.

Alertmanager follows the same boundary. Provider Core Validation proves only the
Alertmanager API contract. `observability/alert_source/providers/alertmanager/binding_profiles.py` resolves
`kubernetes-alerts-v1`, `object-storage-alerts-v1`, and future alert consumer profiles by
asset type. Non-global bindings own their alert identity selector and validation
evidence, allowing one shared Alertmanager to safely serve multiple alert families.

See `docs/architecture/integration-module-map.md` and the README inside each
provider module.

### Metrics Source identity and horizon routing

Metrics Source is one canonical integration category. Product identity is supplied by
the provider catalog and persists as `MetricsSource.provider_key`; backend execution is
selected by `adapter_key`; query semantics are declared through `query_language`.
Operator registration uses one provider-neutral route family under
`/integrations/observability/metrics-sources/`.

A metrics consumer may bind multiple eligible sources to the same asset. Every binding
owns a provider-neutral routing policy:

```text
query_horizon = recent | historical | balanced
weight        = 1..100
```

`METRICS_RECENT_WINDOW_HOURS` defines the recent-data boundary (24h by default).
Instant/current queries request the recent horizon. Point-in-time and range queries
select recent or historical from their actual time boundary. Resolution is deterministic
and safety-first: eligibility and runtime health are evaluated before horizon preference;
role (`Primary → Secondary → Fallback`) remains the failover tier; routing weight ranks
sources inside the same horizon and role; lower priority breaks remaining ties. A horizon
mismatch is a fallback, not a hard rejection.

Current provider definitions may use different default horizons, but consumer code never
branches on provider labels. Adding another product that uses an existing adapter is a
catalog change; adding a different protocol/query language adds an adapter/profile while
the DB, routes, resolver, bindings, and consumer domains remain unchanged.

## UI workspace contract

The implemented Integrations presentation and interaction contract is `docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md`. The original findings and implementation disposition are recorded in `docs/design/audits/INTEGRATIONS_FULL_AUDIT_20260731.md`.

Shared Integrations templates own semantic status adaptation, registry controls, loading, pagination, and bright-evidence hierarchy. Provider packages retain factual compatibility, capability, binding, runtime, and lifecycle data. Provider-local runtime-history presentation wrappers and secondary semantic palettes are not allowed.

### Domain landing projection

`/integrations/orchestration`, `/integrations/observability`, and `/integrations/storage` share the same taxonomy-driven landing workspace:

```text
Capability Registry
Provider Registry
Bindings
```

The Provider Registry is built from canonical `IntegrationInstance` rows. The Bindings view contains consumer-source relationships only; native asset-owner/provider relationships are represented by Provider Registry/managed-asset ownership and are never duplicated as self-bindings. Cross-domain sources appear when they target an asset type owned by the domain taxonomy. Provider-specific ORM queries are not allowed in the shared domain service.

Metrics Source and Alertmanager own binding mutation for their respective source families. Kubernetes and MinIO surface bound observability sources as read-only lifecycle inventory. Eligible asset families are registered centrally in `app/integrations/consumer_assets.py`, so adding a future asset such as Vault extends source binding/coverage by adding the asset definition plus compatible consumer profiles instead of a new binding table or product-specific source form.



## Bindings & Consumers Final Lock

Metrics Source and Alertmanager are source-owned mutation workspaces. Their binding registries expose Consumer Asset, provider identity selector, Consumer Profile, Resolver Preference, Binding Validation, Effective Resolution, and Actions with canonical pagination/loading behavior. Resolver preference is safety-first. Metrics sources add query-horizon routing: eligible/healthy sources are ranked by horizon match, then `Primary → Secondary → Fallback`, then routing weight, with lower numeric priority breaking remaining ties inside the same role/weight.

A saved binding starts in `Validation Required`. Selector changes clear stale binding evidence and return the record to `Validation Required`; a successful `binding.validate` operation grants binding eligibility. Provider Full Validation refreshes every enabled consumer binding after the provider-core checks complete, while the explicit binding Validate action remains available for targeted revalidation. Object Storage binding validation additionally persists canonical metric-family, label-schema, and executable-query readiness so Analytics can distinguish contract gaps from current runtime reachability. Kubernetes and Object Storage inventory/lifecycle pages show the relationship read-only and link operators back to the source workspace for mutation.
