# Metrics Source Integration Module

## Purpose

This package is KAORI's canonical provider-neutral Metrics Source integration
module. It owns backend-adapter dispatch, provider-core validation, versioned
query contracts, asset-scoped binding validation, capability translation, and
runtime-state projection.

Provider identity is data, not architecture. `provider_key` identifies the
registered product, `adapter_key` selects the backend implementation, and
`query_language` records the query contract exposed by that provider. Consumer
domains depend only on the Metrics Source integration contract.

## Files

- `__init__.py`: registers the `metrics_source` module with the Integration Registry.
- `providers.py`: loads provider definitions from the Definition Registry.
- `adapter.py`: backend-adapter registry, query-session contract, operation dispatch, and shared runtime-state translation.
- `prometheus_http_client.py`: Prometheus HTTP API transport used only by providers selecting the `prometheus_http` adapter.
- `prometheus_http_runtime.py`: runtime implementation for the `prometheus_http` adapter.
- `prometheus_http_validation.py`: core-validation implementation for the `prometheus_http` adapter.
- `capabilities.py`: provider-neutral capability keys and runtime projection.
- `exceptions.py`: stable Metrics Source transport/query failures.
- `binding_profiles.py`: `(adapter_key, asset_type)` consumer-validation profile registry.
- `binding_validators/`: adapter-qualified asset validators.
- `query_profiles/`: versioned semantic query expressions and audits used by current adapters.

## Registry contract

| Operation | Queue | Meaning |
|---|---|---|
| `validation.session.build` | `inline` | Build the adapter-specific validation session consumed only by that adapter's registered binding validators. |
| `query.session.build` | `inline` | Build a reusable `MetricsQuerySession` for one resolved source/scope. |
| `query.instant` | `inline` | Execute one current-value expression through the selected backend adapter. |
| `query.at` | `inline` | Execute one point-in-time expression through the selected backend adapter. |
| `query.range` | `inline` | Execute one range expression through the selected backend adapter. |
| `connection.test` | `inline` | Test draft or persisted endpoint transport and adapter compatibility. |
| `query_profile.audit` | `integration-validation` | Audit the configured adapter/query contract without owning consumer readiness. |
| `runtime.validate` | `integration-validation` | Validate provider identity, adapter compatibility, and provider-owned execution capabilities. |
| `runtime.health` | `integration-runtime` | Run a lightweight endpoint health observation. |
| `runtime.state` | `inline` | Translate provider evidence into the shared runtime state. |
| `binding.create` | `inline` | Create a provider-neutral managed-asset binding. |
| `binding.selector.update` | `inline` | Update the binding selector and invalidate prior binding evidence. |
| `binding.validate` | `integration-validation` | Validate the `(adapter_key, asset_type)` consumer profile selected by the binding. |

## Persistence and binding

`MetricsSource` in `app/models/metrics_source.py` stores one reusable source.
`IntegrationInstance.provider_type` is always `metrics_source`; individual
products never become canonical integration categories. `IntegrationBinding`
is the only source-to-asset binding table and owns consumer profile, selector,
routing policy, and validation evidence.

A Kubernetes cluster, object-storage system, or future managed asset can share
one Metrics Source or bind multiple sources without embedding product-specific
foreign keys or credentials in the consumer domain.

## Provider and adapter contract

Provider definitions are loaded from
`app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml` and declare:

```text
provider_key
adapter_key
query_language
default_query_horizon
version_detection_mode
endpoint_capabilities
compatibility profile options
presentation metadata
```

Adding another product that implements an existing adapter requires a provider
definition and, when applicable, compatibility metadata. Adding a source with a
different API or query language requires a new backend adapter/query translator
and its binding-validation profiles, but does not change the Metrics Source DB
schema, routes, resolver, managed-asset bindings, or analytics consumers.

## Consumer binding ownership

`Bindings & Consumers` is owned by the Metrics Source workspace. It uses the
canonical managed-asset registry and resolves the consumer profile by
`adapter_key + asset_type`. Asset-owner pages display the resulting source
bindings read-only and never create pair-specific binding tables or forms.

Full Validation is provider-core only and never refreshes consumer bindings
implicitly. Provider readiness therefore remains consumer-neutral. The explicit
explicit binding Validate action is the only path that rebuilds one consumer's
identity, metric-label, retention, and capability evidence.

Kubernetes consumer bindings use one canonical identity contract: `cluster=<stable-cluster-name>`. For direct Prometheus, the label must be query-visible on Kubernetes scrape targets because KAORI applies the binding selector to PromQL. When the source feeds Thanos, every upstream Prometheus must also publish the same cluster value as an external label so the aggregated query plane preserves provenance. Storage filesystem evidence additionally requires `node=<Kubernetes Node.name>` on `node_filesystem_size_bytes` and `node_filesystem_avail_bytes`, paired on the same mountpoint (`/var` preferred, `/` fallback). The `instance` label is not a node-identity substitute. Missing consumer identity and label evidence is persisted on `IntegrationBinding.validation_evidence` and surfaced from the corresponding binding through `View Result`; Provider Readiness remains provider-core only.

## Query runtime contract

`MetricsConsumer` is the only analytics query boundary. It resolves an eligible
source, requests a generic `MetricsQuerySession`, reuses that session within the
dataset execution, and invokes only `query.instant`, `query.at`, or
`query.range`. The consumer never imports a product client or calls a
product-specific client method.

Query-horizon routing (`recent`, `historical`, `balanced`) is source-neutral.
Provider labels are presentation metadata; routing and failover operate on
binding eligibility, runtime health, role, horizon, weight, and priority.

## Manage UI and lifecycle contract

Metrics Sources are registered as reusable provider records. Every instance has
one canonical manage workspace containing Configuration, Validation &
Capabilities, Runtime & History, and Scope & Resolution. Product selection is
performed through the provider catalog, while route structure remains the same
for every provider.

Instance deletion is a governed database lifecycle action and has no live
external-endpoint dependency. Every source binding must be removed first,
including disabled bindings, and active provider jobs block deletion.
Historical runtime observations and Activity Audit records remain available.

## Canonical application boundary

The web/domain package under `app/integrations/observability/metrics_source/application` calls provider operations only
through the Integration Registry. Backend implementation belongs in this
package and must not leak into Kubernetes, Object Storage, Reports,
Intelligence, Dashboard, or other consumer domains.
