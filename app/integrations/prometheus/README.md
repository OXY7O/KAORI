# Prometheus Integration Module

## Purpose

This package is the canonical Prometheus/Thanos provider module. It owns HTTP
transport, provider-neutral core validation, consumer PromQL query contracts,
capability definitions, asset-scoped validation evidence, compatibility profiles,
and runtime translation.

## Files

- `__init__.py`: registers the provider module with the integration registry.
- `adapter.py`: operation dispatch and shared runtime-state translation.
- `client.py`: Prometheus-compatible HTTP API transport.
- `capabilities.py`: capability keys and supported runtime profiles.
- `exceptions.py`: provider transport and query failures.
- `core_validation.py`: provider-neutral Prometheus API validation (`prometheus-core-v1`).
- `binding_profiles.py`: asset-scoped consumer validation profile registry.
- `query_profiles/`: versioned consumer PromQL definitions, feature contracts, and audits.

## Registry contract

| Operation | Queue | Meaning |
|---|---|---|
| `client.build` | `inline` | Build a scoped or unscoped provider client; no network call. |
| `connection.test` | `inline` | Test draft or persisted endpoint identity and compatibility. |
| `query_profile.audit` | `integration-validation` | Legacy Kubernetes consumer audit entry point; it does not own provider readiness. |
| `runtime.validate` | `integration-validation` | Validate endpoint compatibility and provider-neutral Prometheus core APIs. |
| `runtime.health` | `integration-runtime` | Run a lightweight endpoint health observation. |
| `runtime.state` | `inline` | Translate provider evidence into shared runtime state. |
| `binding.create` | `inline` | Create a provider-neutral managed-scope binding. |
| `binding.selector.update` | `inline` | Update the scope selector and invalidate prior binding evidence. |
| `binding.validate` | `integration-validation` | Validate the asset-scoped consumer profile selected by the binding (`Kubernetes Metrics v1`, provider-neutral `Object Storage Metrics v1`, or future profiles). Object Storage then selects a provider-qualified validator such as MinIO Metrics v2. |

## Persistence and binding

`PrometheusInstance` in `app/models/prometheus.py` stores one reusable metrics
source. `IntegrationBinding` is the only scope-binding table and owns the
consumer validation profile/evidence for each managed asset. Kubernetes, MinIO,
and future consumers may therefore share one Prometheus provider without making
provider readiness depend on any single exporter family. Analytics resolves an
eligible source through the provider resolver and never reads credentials or a
cluster-owned configuration.

## Compatibility

Endpoint product/version detection and the declared Prometheus source profile
are separate. Thanos may expose Prometheus-compatible query APIs without a
Prometheus `/version` identity. Provider Full Validation establishes endpoint
compatibility and the `prometheus-core-v1` API contract only. Exporter/domain
metrics, labels, and consumer PromQL contracts are validated through each
`IntegrationBinding` and stored as binding evidence.

Full Validation refreshes enabled consumer bindings after provider-core validation.
This keeps provider readiness consumer-neutral while rebuilding binding-owned evidence in
the same operator workflow. The binding-level Validate action remains the targeted path
when only one consumer needs to be rechecked.

## Source-owned consumer binding UX

Prometheus is the mutation owner for its consumer bindings. `Bindings & Consumers` uses
one shared `Add Binding` modal backed by the canonical managed-asset registry. Current
eligible asset families are Kubernetes clusters and object-storage systems; the selected
asset type resolves `kubernetes-metrics-v1` or the provider-neutral `object-storage-metrics-v1` automatically. Object Storage validation then resolves a provider-qualified metric adapter such as MinIO Metrics v2.
Asset-owner pages show the resulting Prometheus source read-only and do not create or
remove the binding themselves.

Adding a future managed asset such as Vault requires registering its asset definition and
a compatible Prometheus consumer profile (for example `vault-metrics-v1`). It must not
require a Vault-specific Prometheus form or binding table.

## Prometheus Manage UI and lifecycle contract

Prometheus and Prometheus-compatible query endpoints are registered as reusable
provider instances. Each instance has one canonical manage workspace containing
Configuration, Validation & Capabilities, Runtime & History, and Scope &
Resolution. Provider-local configuration pages and cluster-scoped bookmark
routes are not part of the active contract.

### Instance deletion

Instance deletion is a governed database lifecycle action and has no live
Prometheus or Thanos dependency. Every provider-neutral scope binding must be
removed first, including disabled bindings. Active provider jobs also block the
operation. KAORI repeats these checks in the service boundary before deleting
the provider record and its canonical integration identity atomically.

Historical runtime observations and Activity Audit records remain available.
The delete control is therefore shown only in the contextual Scope & Resolution
workspace, next to its binding and job blockers.

## Canonical application boundary

Provider runtime and binding behavior is implemented in `runtime.py`,
`binding_management.py`, `binding_validation.py`, and `scope.py`. The adapter
dispatches every operation directly to those modules. This package must not
import `app.prometheus`; the web/domain package calls it only through the
Integration Registry.
