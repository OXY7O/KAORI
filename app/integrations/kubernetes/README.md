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
- `tls.py`: bounded operator-approved weak-TLS context.

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
