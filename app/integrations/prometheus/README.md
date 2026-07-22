# Prometheus Integration Module

## Purpose

This package is the canonical Prometheus/Thanos provider module. It owns HTTP
transport, PromQL query contracts, capability definitions, validation evidence,
compatibility profiles, and runtime translation.

## Files

- `__init__.py`: registers the provider module with the integration registry.
- `adapter.py`: operation dispatch and shared runtime-state translation.
- `client.py`: Prometheus-compatible HTTP API transport.
- `capabilities.py`: capability keys and supported runtime profiles.
- `exceptions.py`: provider transport and query failures.
- `query_profiles/`: canonical versioned PromQL definitions, feature contracts, and audits.

## Registry contract

| Operation | Queue | Meaning |
|---|---|---|
| `client.build` | `inline` | Build a scoped or unscoped provider client; no network call. |
| `connection.test` | `inline` | Test draft or persisted endpoint identity and compatibility. |
| `query_profile.audit` | `integration-validation` | Run the canonical PromQL feature-contract audit. |
| `runtime.validate` | `integration-validation` | Run full compatibility, metric, label, query, and retention validation. |
| `runtime.health` | `integration-runtime` | Run a lightweight endpoint health observation. |
| `runtime.state` | `inline` | Translate provider evidence into shared runtime state. |
| `binding.create` | `inline` | Create a provider-neutral managed-scope binding. |
| `binding.selector.update` | `inline` | Update the scope selector and invalidate prior binding evidence. |
| `binding.validate` | `integration-validation` | Validate scoped Kubernetes identity metrics. |

## Persistence and binding

`PrometheusInstance` in `app/models/prometheus.py` stores one reusable source.
`IntegrationBinding` is the only scope-binding table. Analytics resolves an
eligible source through the provider resolver and never reads credentials or a
cluster-owned configuration.

## Compatibility

Endpoint product/version detection and the declared Prometheus source profile
are separate. Thanos may expose Prometheus-compatible query APIs without a
Prometheus `/version` identity. Full Validation therefore treats successful
query contracts and observed labels/series as authoritative evidence.

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
