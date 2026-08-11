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
    │   └── MinIO
    ├── File Storage
    └── Block Storage
```

`worker_domain` remains execution metadata and must not be reused as the UI or
architecture taxonomy. `taxonomy.py` is the canonical domain/capability map.


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
`cluster.*`, `prometheus.*`, and `alertmanager.*` to retain the correct domain active state
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
4. **Consumer Eligibility** is derived from the validated binding evidence and
   the capabilities required by the Inventory, Analytics, Governance, or
   Operations consumer.
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

Prometheus is the canonical example. `prometheus-core-v1` owns provider Core
Validation. `prometheus/binding_profiles.py` selects the consumer profile by
asset type: Kubernetes registers `kubernetes-metrics-v1`; MinIO registers
`minio-metrics-2024-v1`. One Prometheus provider can therefore serve both assets
with independent selectors, evidence, and binding readiness.

See `docs/architecture/integration-module-map.md` and the README inside each
provider module.

## UI workspace contract

The implemented Integrations presentation and interaction contract is `docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md`. The original findings and implementation disposition are recorded in `docs/design/audits/INTEGRATIONS_FULL_AUDIT_20260731.md`.

Shared Integrations templates own semantic status adaptation, registry controls, loading, pagination, and bright-evidence hierarchy. Provider packages retain factual compatibility, capability, binding, runtime, and lifecycle data. Provider-local runtime-history presentation wrappers and secondary semantic palettes are not allowed.
