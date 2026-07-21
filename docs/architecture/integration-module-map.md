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
| `app/integrations/registry.py` | Provider registration, operation dispatch, instance loading, and operation-to-queue mapping. |
| `app/integrations/runtime/` | Shared runtime observation, scoring, monitoring, persistence, and presentation. |
| `app/integrations/validation/` | Canonical asynchronous validation and runtime-refresh orchestration. |
| `app/integrations/lifecycle.py` | Canonical `IntegrationInstance` and `IntegrationBinding` lifecycle. |
| `app/integrations/deletion.py` | Provider-neutral dependency and active-job deletion guards. |

## Provider modules

| Provider | Module | Primary worker domain | Operations |
|---|---|---|---|
| Kubernetes | `app/integrations/kubernetes/` | `kubernetes` | `client.build`, `runtime.validate`, `runtime.health`, `runtime.state`, `inventory.sync` |
| Prometheus | `app/integrations/prometheus/` | `observability-metrics` | `client.build`, `runtime.validate`, `runtime.health`, `runtime.state` |
| Alertmanager | `app/integrations/alertmanager/` | `observability-alerts` | `client.build`, `runtime.validate`, `runtime.health`, `runtime.state` |

Every registered operation has an explicit execution queue. Inline operations
are construction or state-translation operations that perform no asynchronous
work.

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
2. **Application URL compatibility** is limited to GET-only redirects for old
   bookmarks. Old URLs do not expose POST, validation, delete, or runtime
   operations and do not retain legacy persistence or Python import facades.

Current URL compatibility sunset: **31 December 2026**.

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

Celery Beat dispatches schedules only. It performs no provider I/O. Every
provider operation is registered with a queue so a new caller cannot silently
fall into an unconsumed default queue.

## Adding a new integration

1. Add `app/integrations/<provider>/` with adapter, client, capabilities,
   validation, schemas, and README.
2. Implement `RuntimeAdapter` and stable operation keys.
3. Register one `IntegrationModule` with explicit queue mapping, capability
   keys, and compatibility profiles.
4. Add provider-specific mapped model under `app/models/` only when required.
5. Add domain service and route that call the registry rather than the client.
6. Add canonical `JobExecution` orchestration for asynchronous operations.
7. Add deletion dependencies, audit events, and permission coverage.
8. Add contract, migration, registry, and route tests.
9. Do not add a second binding table, credential column, runtime table, or full
   legacy blueprint.
