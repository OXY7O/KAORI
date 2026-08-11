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
| `app/integrations/registry.py` | Provider registration, taxonomy ownership, operation dispatch, provider/canonical record loading, workspace routing, failure hooks, and operation-to-queue mapping. |
| `app/integrations/binding_service.py` | Provider-neutral source-to-asset binding entrypoint with domain compatibility wrappers. |
| `app/integrations/runtime/` | Shared runtime observation, scoring, monitoring, persistence, and presentation. |
| `app/integrations/validation/` | Canonical asynchronous validation and runtime-refresh orchestration. |
| `app/integrations/lifecycle.py` | Canonical `IntegrationInstance` and `IntegrationBinding` lifecycle. |
| `app/integrations/deletion.py` | Provider-neutral dependency and active-job deletion guards. |

## Provider modules

| Domain | Capability | Provider | Module | Primary worker domain |
|---|---|---|---|---|
| Orchestration | Cluster Orchestration | Kubernetes | `app/integrations/kubernetes/` | `kubernetes` |
| Observability | Metrics | Prometheus | `app/integrations/prometheus/` | `observability-metrics` |
| Observability | Alerting | Alertmanager | `app/integrations/alertmanager/` | `observability-alerts` |
| Storage | Object Storage | MinIO | future `app/integrations/minio/` | future provider registration |

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
foreign keys. Existing Kubernetes clusters bind Kubernetes API, Prometheus, and
Alertmanager providers to `kubernetes_cluster:<cluster-id>`. Object storage will
follow the same pattern: MinIO API and Prometheus metrics providers bind to the
same `object_storage_system:<asset-id>` scope.


## Domain boundaries

| KAORI domain | Owns | Must not own |
|---|---|---|
| `app/cluster/` | Managed Kubernetes asset lifecycle and UI workflow. | Kubernetes transport, compatibility implementation, or duplicated kubeconfig. |
| `app/inventory/` | Inventory persistence, normalization, and inventory business rules. | Kubernetes credentials or client construction. |
| `app/analytics/` | Analytics policy, query selection, aggregation, caching, and view models. | Prometheus credentials or raw provider selection. |
| `app/kubernetes_operations/` | ConfigMap/Secret operational policy, authorization, confirmation, and audit. | Kubernetes transport construction. |
| `app/governance/` | Governance policy and interpretation. | Kubernetes credential persistence. |
| `app/prometheus/` | Prometheus registration forms, domain services, source resolution, bindings UI, and presentation. | Transport, query profiles, compatibility implementation, or runtime adapter implementation. |
| `app/alertmanager/` | Alertmanager registration forms, domain services, source resolution, bindings UI, and presentation. | Transport, normalizers, compatibility implementation, or runtime adapter implementation. |

SQLAlchemy models remain centralized under `app/models/`. Provider packages do
not define mapped database models.

## Canonical persistence

```text
IntegrationInstance
    ├── KubernetesConnection
    ├── PrometheusInstance
    └── AlertmanagerInstance

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

Compatibility exists at two different layers and must not be confused:

1. **Provider compatibility profiles** are supported runtime contracts such as
   Kubernetes API lifecycle bands, Prometheus v2/v3 query contracts, and
   Alertmanager v0.25/v0.33 API contracts.
2. **Application compatibility layers are not retained.** Replaced URLs return
   `404`, retired Python import paths are removed, and persisted transition fields
   are converted by an explicit Alembic migration. External runtime compatibility
   remains implemented only through provider profiles and capability evidence.

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
3. Register one `IntegrationModule` with `domain_key`, `capability_key`, catalog/workspace metadata, reverse canonical-record loading, explicit queue mapping, capability keys, and compatibility profiles.
4. Add provider-specific mapped model under `app/models/` only when required.
5. Add domain service and route that call the registry rather than the client.
6. Add canonical `JobExecution` orchestration for asynchronous operations.
7. Add deletion dependencies, audit events, and permission coverage.
8. If the provider is consumed through Prometheus, register an asset-specific Prometheus binding validation profile instead of adding probes to the shared validator.
9. Add contract, migration (only when persistence changes), registry, and route tests.
10. Do not add a second binding table, provider-to-provider foreign key, credential column, runtime table, or full legacy blueprint.
