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
│   │   └── Prometheus
│   └── Alerting
│       └── Alertmanager
└── Storage
    ├── Object Storage
    │   └── provider modules such as MinIO
    ├── File Storage
    └── Block Storage
```

`worker_domain` remains execution metadata and must not be reused as the UI or
architecture taxonomy. `taxonomy.py` is the canonical domain/capability map.

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
├── Prometheus metrics provider
└── Alertmanager alerting provider

Object Storage System
├── MinIO API provider
└── Prometheus metrics provider
```

New domains must reuse `IntegrationBinding`; do not introduce pair-specific
binding tables such as `minio_prometheus_bindings`.

## Rules

- Cross-domain callers resolve integrations with `get_integration()` or
  `execute_integration_operation()`.
- Provider clients and compatibility logic live under
  `app/integrations/<provider>/`.
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
- `taxonomy.py`: stable integration domains and capabilities.
- `registry.py`: registration, taxonomy ownership, lookup, dispatch, model
  loading, detail routing, failure hooks, and queue map.
- `binding_service.py`: provider-neutral source-to-asset binding entrypoint plus
  domain compatibility wrappers.

## Validation levels

1. **Test Connection** verifies submitted endpoint identity and reachability.
2. **Full Capability Validation** rebuilds compatibility, capabilities, and
   technical evidence using `integration-validation` workers.
3. **Scope Binding Validation** proves that a registered source can serve the
   selected operational scope and persists selector/evidence state.
4. **Runtime Refresh** performs lightweight health observation using
   `integration-runtime` workers.

The full-validation worker dispatches through the registry and does not branch
on provider names. Providers with `binding.validate` automatically participate
in binding refresh. Provider-specific failure persistence is exposed through a
registered hook.

Prometheus binding validation is selected by asset type through
`prometheus/binding_profiles.py`. Kubernetes registers the initial
`kubernetes_cluster` profile; object-storage providers add their own identity
probe profile without modifying the shared validator.

See `docs/architecture/integration-module-map.md` and the README inside each
provider module.

## UI workspace contract

The implemented Integrations presentation and interaction contract is `docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md`. The original findings and implementation disposition are recorded in `docs/design/audits/INTEGRATIONS_FULL_AUDIT_20260731.md`.

Shared Integrations templates own semantic status adaptation, registry controls, loading, pagination, and bright-evidence hierarchy. Provider packages retain factual compatibility, capability, binding, runtime, and lifecycle data. Provider-local runtime-history presentation wrappers and secondary semantic palettes are not allowed.
