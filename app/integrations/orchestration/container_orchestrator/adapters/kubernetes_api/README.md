# Kubernetes Integration Module

## Purpose

This package is the canonical Kubernetes provider module. It owns Kubernetes
transport construction, API discovery, compatibility selection, capability
translation, validation, runtime state, inventory dispatch, and provider action
contracts.

## Files

- `__init__.py`: registers the provider module with the integration registry.
- `adapter.py`: operation dispatch, inventory delegation, and runtime-state translation.
- `client.py`: Kubernetes Python client construction.
- `capabilities.py`: capability keys and supported runtime profiles.
- `compatibility.py`: served-API discovery and version-aware adapter selection.
- `validation.py`: connection, version, RBAC, and runtime validation.
- `resolver.py`: canonical cluster-to-connection resolution.
- `tls.py`: operator-approved legacy cipher policy scoped to each Kubernetes SDK API client; no process-global TLS overrides.

## Registry contract

| Operation | Queue | Meaning |
|---|---|---|
| `client.build` | `inline` | Build a client from `KubernetesConnection`; no network call. |
| `runtime.validate` | `integration-validation` | Full connection and compatibility validation. |
| `runtime.health` | `integration-runtime` | Lightweight health observation. |
| `runtime.state` | `inline` | Translate provider state into shared runtime state. |
| `inventory.sync` | `inventory` | Collect and persist Kubernetes inventory. |

## Persistence

`KubernetesConnection` in `app/models/kubernetes.py` is the only connection and
credential authority. `Cluster` is the managed asset record and never stores
kubeconfig, endpoint, or TLS policy.

## Compatibility

The compatibility profile is selected from discovered Kubernetes version and
available API resources. Stable API candidates are preferred; tested legacy API
adapters may be selected only when declared by the compatibility contract.
Blocked or unsupported API requirements degrade or block readiness with stored
evidence.

## Connection Registry and Coverage read model

The Kubernetes front page performs provider lifecycle, selected source/binding
coverage, operator filters and complete-fleet counters in SQL via
`container_orchestrator/fleet_query.py`. It selects independent Registry and
Coverage pagination windows (default five) **before** hydrating full provider
records and reusable Metrics Source/Alertmanager bindings. The shared source
lookup is limited to the visible cluster IDs and canonical source identities.
All runtime operations and provider state remain Kubernetes-owned.

### Legacy TLS import compatibility during DevContainer review

The provider client is authoritative for any explicitly approved weak-TLS
policy: it applies TLS configuration to its own urllib3 transport, never to
process-wide TLS defaults. The retired `weak_tls_context(enabled=...)` symbol
is temporarily retained as a **no-op import compatibility bridge** for any
older callers not yet migrated. It does not change TLS behavior and must not
be used by new code. Existing operations must build Kubernetes API clients via
`container_orchestrator → client.build`, which reads the canonical connection
`allow_weak_tls` flag. The import-regression contract scans application
modules for old imports so this bridge can be removed after complete migration.
