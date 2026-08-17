# KAORI Integration Module Map

## Architecture decision

KAORI remains a modular monolith. Integration code is isolated behind a shared
kernel so provider modules can be reviewed, tested, scaled, or extracted later
without rewriting business domains.

```text
HTTP Route / Celery Task
        ↓
Domain Service
        ↓
Integration Registry
        ↓
Provider Adapter
        ↓
Provider Client / External API
```

A route owns HTTP concerns. A domain service owns KAORI business policy. The
registry resolves a provider by a stable key. The adapter owns provider
operations, compatibility and runtime translation. The provider client owns the
wire protocol.

## Shared integration kernel

| Module | Ownership |
|---|---|
| `app/integrations/contracts/` | Provider-neutral adapter, capability, result, and exception contracts. |
| `app/integrations/taxonomy.py` | Canonical integration domain and capability taxonomy used by registry and presentation. |
| `app/integrations/registry.py` | Provider registration, taxonomy ownership, operation dispatch, provider/canonical record loading, workspace routing, navigation ownership, failure hooks, and operation-to-queue mapping. |
| `app/integrations/binding_service.py` | Provider-neutral source-to-asset binding entrypoint using canonical `SourceBindingSpec`; domain compatibility wrappers are prohibited. |
| `app/integrations/navigation.py` | Registry-driven sidebar domain projection and provider endpoint ownership. |
| `app/integrations/runtime/` | Shared runtime observation, scoring, monitoring, persistence, and presentation. |
| `app/integrations/validation/` | Canonical asynchronous validation and runtime-refresh orchestration. |
| `app/integrations/lifecycle.py` | Canonical `IntegrationInstance` and `IntegrationBinding` lifecycle. |
| `app/integrations/deletion.py` | Provider-neutral dependency and active-job deletion guards. |

## Provider modules

| Domain | Capability | Provider | Module | Primary worker domain |
|---|---|---|---|---|
| Orchestration | Cluster Orchestration | Kubernetes | `app/integrations/kubernetes/` | `kubernetes` |
| Observability | Metrics | Metrics Source | `app/integrations/metrics/` | `observability-metrics` |
| Observability | Alerting | Alertmanager | `app/integrations/alertmanager/` | `observability-alerts` |
| Storage | Object Storage | MinIO | `app/integrations/minio/` | `storage-object` |

Every registered operation has an explicit execution queue. Inline operations
are construction or state-translation operations that perform no asynchronous
work.

`worker_domain` is execution routing metadata. The architecture and UI taxonomy
comes from `domain_key` and `capability_key` registered on `IntegrationModule`.

## Provider and asset binding architecture

`IntegrationBinding` remains the only canonical provider binding persistence.
The relation is provider-to-asset, not provider-to-provider:

```text
IntegrationInstance
        │
        └── IntegrationBinding(asset_type, asset_key)
                              │
                              ▼
                         Managed Asset
```

This lets different provider types serve one managed asset without pair-specific
foreign keys. Existing Kubernetes clusters bind Kubernetes API, Metrics Source, and
Alertmanager providers to `kubernetes_cluster:<cluster-id>`. Object Storage follows
the same pattern: MinIO API, Metrics Source, and Alertmanager providers bind
to the same `object_storage_system:<asset-id>` scope.


### Object Storage metrics validation boundary

Metrics Source binding validation registers one provider-neutral Object Storage
consumer profile (`object-storage-metrics-v1`). The validation implementation
then resolves a provider-qualified adapter. MinIO currently maps to the
`minio-v2` audit contract, which validates scoped metric families, label schema,
and executable canonical queries before persisting `metrics_readiness` evidence
on the binding. This is deliberately separate from interactive Analytics runtime
queries and from provider-core Metrics Source readiness.

### Analytics metrics-source boundary

Object Storage Analytics does not depend directly on a Metrics Source product. It resolves a
provider-neutral `MetricsSource` and then selects a qualified
**asset-provider + metrics-provider** adapter. The first pair is MinIO +
the selected Metrics Source. A metrics binding for a different Object Storage provider must
not reuse MinIO PromQL implicitly; that provider requires its own qualified
adapter/profile. See `domain-namespace-and-metrics-source-boundary.md`.


## Domain boundaries

| KAORI domain | Owns | Must not own |
|---|---|---|
| `app/cluster/` | Managed Kubernetes asset lifecycle and UI workflow. | Kubernetes transport, compatibility implementation, or duplicated kubeconfig. |
| `app/inventory/` | Capability root with explicit `kubernetes/` and `object_storage/` domain ownership for committed inventory state. | Mixed-domain implementation at the capability root, provider credentials, or client construction. |
| `app/analytics/` | Capability root with explicit `kubernetes/` and `object_storage/` domains plus genuinely provider-neutral `shared/` contracts. | Mixed-domain implementation, provider credentials, or provider query/payload semantics in domain services. |
| `app/kubernetes_operations/` | ConfigMap/Secret operational policy, authorization, confirmation, and audit. | Kubernetes transport construction. |
| `app/governance/` | Governance policy and interpretation. | Kubernetes credential persistence. |
| `app/metrics/` | Metrics Source registration forms, provider selection, domain services, source resolution, bindings UI, and presentation. | Backend transport, query profiles, compatibility implementation, or runtime adapter implementation. |
| `app/alertmanager/` | Alertmanager registration forms, domain services, source resolution, bindings UI, and presentation. | Transport, normalizers, compatibility implementation, or runtime adapter implementation. |

SQLAlchemy models remain centralized under `app/models/`. Provider packages do
not define mapped database models.

## Canonical persistence

```text
IntegrationInstance
    ├── KubernetesConnection
    ├── MetricsSource
    ├── AlertmanagerInstance
    └── MinioInstance

ObjectStorageSystem
    └── provider-neutral managed asset for MinIO today and future object-storage providers

IntegrationBinding
    └── provider-neutral scope binding

IntegrationRuntimeObservation
    └── provider-neutral runtime evidence

JobExecution
    └── provider-neutral asynchronous lifecycle
```

There is one credential authority per provider instance. `Cluster` is a managed
asset and does not store kubeconfig, endpoint, or TLS connection policy.

## Compatibility policy

Canonical validation flow:

```text
IntegrationModule / Provider
        ↓
Compatibility Profile
        ↓
Provider Capability Set
        ↓
Provider Core Validation
        ↓
IntegrationInstance Ready
        ↓
IntegrationBinding
        ↓
Consumer Profile
        ↓
Binding Validation Evidence
        ↓
Effective Consumer Eligibility
```

Provider Core Validation is product/version/API scoped. Consumer Profile
validation is asset/binding scoped. A provider may have many bindings, and each
binding may have a different consumer profile and readiness state.
Execution capabilities remain provider-core evidence; asset identity, selector, and domain metric eligibility remain Binding Validation evidence. Consumer source resolution must combine both boundaries without copying provider transport capabilities into each binding.

Compatibility exists at two different layers and must not be confused:

1. **Provider compatibility profiles** are supported runtime contracts such as
   Kubernetes API lifecycle bands, Metrics Source provider/adapter compatibility, and
   Alertmanager v0.25/v0.33 API contracts. Metrics Source readiness uses the
   provider-neutral adapter contract; exporter/domain metric contracts
   are owned by asset-scoped bindings.
2. **Application compatibility layers are not retained.** Replaced URLs return
   `404`, retired Python import paths are removed, and persisted transition fields
   are converted by an explicit Alembic migration. External runtime compatibility
   remains implemented only through provider profiles and capability evidence.

### Metrics Source consumer-profile boundary

One Metrics Source may serve multiple managed-asset types, and one asset may bind
multiple Metrics Sources. Provider Core Validation establishes provider identity,
backend-adapter compatibility, and provider-owned execution capabilities only.
Asset-specific metric families, selectors, and evidence live on
`IntegrationBinding`.

Binding-profile and validator selection is keyed by `adapter_key + asset_type`.
This lets a provider that reuses an existing backend adapter become catalog-driven,
while a provider with a different protocol/query language adds its own adapter and
profiles without changing the DB schema, routes, resolver, or consumer domains.

The Metrics Source resolver evaluates consumer eligibility from binding evidence and
runtime health, then applies horizon, role, routing weight, and priority. Product
labels are never resolver branches.

### Alertmanager consumer-profile boundary

One Alertmanager provider may receive alerts for many managed-asset types.
Provider Full Validation establishes only endpoint compatibility and the core
Status, Alerts, and Silences API v2 contract. `IntegrationBinding.validation_profile`
selects the alert consumer contract and `IntegrationBinding.validation_evidence`
stores selector-scoped payload evidence. Current canonical profiles include
`kubernetes-alerts-v1` for `kubernetes_cluster` and `object-storage-alerts-v1` for
`object_storage_system`. Non-global bindings require a stable alert identity
selector so a shared Alertmanager can segregate Kubernetes, MinIO, infrastructure,
and future alert streams. The resolver evaluates eligibility from binding evidence,
not provider-wide active-alert payload state.

Alert rules are evaluated upstream by the configured alert/metrics pipeline. Their presence or
absence is not Alertmanager provider-readiness evidence. A consumer-profile failure
changes only the affected binding.

### Provider workspace alignment

Kubernetes, Metrics Source, Alertmanager, and MinIO follow the same provider interaction
model for front pages, registration, Configuration, Validation & Capabilities, and Runtime &
History. Asset-owner providers use a lifecycle-oriented final workspace: Kubernetes
owns the managed cluster lifecycle and MinIO owns the canonical `object_storage_system`
lifecycle, while Metrics Source and Alertmanager remain reusable shared-source providers.
Kubernetes and MinIO expose `Inventory & Lifecycle`, where bound observability sources are
read-only evidence. Metrics Source/Alertmanager own binding creation, validation, update, and
removal from their `Bindings & Consumers` workspaces. Provider-specific API fields and
consumer contracts may differ, but Hero semantics, connection terminology, readiness
boundaries, standard tables, and empty/populated registry states must not drift per provider.

Eligible consumer asset families are registered centrally in `app/integrations/consumer_assets.py`.
The shared Observability Add Binding modal resolves each source provider's Consumer Profile from
the selected asset type. A future managed asset such as Vault should register `vault_system` plus
compatible Metrics Source/Alertmanager profiles; it then becomes eligible without a new source-specific
binding form or binding table.

## Worker ownership

| Queue | Workload |
|---|---|
| `inventory` | Kubernetes inventory collection only. |
| `maintenance` | Retention, archive, and reconciliation maintenance. |
| `integration-runtime` | Lightweight provider runtime health refresh. |
| `integration-validation` | Full provider and binding validation. |
| `analytics-batch` | Cached/precomputed analytics workloads. |
| `forecasting` | Forecasting workloads and heavy historical calculations. |
| `reporting` | Report generation/export workloads. |

Queue names for analytics, forecasting, and reporting may be reserved before their task modules exist, but idle production workers must not be deployed. A worker is added only in the same change that registers at least one explicit task route for its queue.

Celery Beat dispatches schedules only. It performs no provider I/O. Every
provider operation is registered with a queue so a new caller cannot silently
fall into an unconsumed default queue.

## Adding a new integration

1. Add `app/integrations/<provider>/` with adapter, client, capabilities,
   validation, schemas, and README.
2. Implement `RuntimeAdapter` and stable operation keys.
3. Register one `IntegrationModule` with `domain_key`, `capability_key`, catalog/workspace metadata, navigation endpoint ownership, reverse canonical-record loading, explicit queue mapping, capability keys, and compatibility profiles.
4. Add provider-specific mapped model under `app/models/` only when required.
5. Add domain service and route that call the registry rather than the client.
6. Add canonical `JobExecution` orchestration for asynchronous operations.
7. Add deletion dependencies, audit events, and permission coverage.
8. If the asset consumes metrics, register an adapter-qualified Metrics Source binding validation profile instead of adding probes to the shared validator.
9. Add contract, migration (only when persistence changes), registry, and route tests.
10. Do not add a second binding table, provider-to-provider foreign key, credential column, runtime table, or full legacy blueprint.


## Integration navigation projection

The authenticated sidebar exposes domain landing pages rather than product names:

```text
Integrations
├── Overview
├── Orchestration
├── Observability
└── Storage
```

Provider workspaces remain canonical deep links. `IntegrationModule.navigation_endpoint_prefixes`
assigns those endpoints to their owning domain, so Kubernetes and `cluster.*` remain active under
Orchestration while Metrics Source and Alertmanager remain active under Observability. The sidebar
does not branch on provider names. Domain landing pages are taxonomy-driven projections over
canonical `IntegrationInstance` identities and active `IntegrationBinding` evidence.

## Domain Landing Registry and Binding Projection

Integration domain landing pages are one shared projection for Orchestration, Observability, and Storage:

```text
Integration taxonomy
  ├── domain
  ├── capability
  └── owned asset_types
          │
          ▼
IntegrationInstance + IntegrationBinding
          │
          ├── Provider Registry
          └── Binding Registry
```

A domain Bindings view includes **consumer bindings** whose source provider belongs to the selected source-oriented domain or whose target `asset_type` is owned by the selected consumer domain. Native asset-owner attachments are excluded from this view and from consumer-binding counts. For example, `Metrics Source → object_storage_system` and `Alertmanager → object_storage_system` are visible from Storage, while MinIO ownership of the same `object_storage_system` is represented by the provider connection itself rather than a MinIO self-binding.

