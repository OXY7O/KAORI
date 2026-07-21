# Prometheus Integration Module

## Purpose

This package is the canonical Prometheus/Thanos provider module. It owns HTTP
transport, PromQL query contracts, capability definitions, validation evidence,
compatibility profiles, and runtime translation.

## Files

- `adapter.py`: registry operations and shared runtime translation.
- `client.py`: Prometheus-compatible HTTP API transport.
- `capabilities.py`: capability catalog and compatibility profiles.
- `validation.py`: provider validation entry point.
- `queries.py`: reusable provider query helpers.
- `query_profiles/`: versioned Analytics PromQL contracts and audit logic.
- `evidence.py`: provider evidence schemas/builders.
- `schemas.py`: provider-owned schemas.

## Registry contract

| Operation | Queue | Meaning |
|---|---|---|
| `client.build` | `inline` | Build a scoped or unscoped provider client; no network call. |
| `runtime.validate` | `integration-validation` | Full compatibility, metric, label, query, and retention validation. |
| `runtime.health` | `integration-runtime` | Lightweight endpoint health observation. |
| `runtime.state` | `inline` | Translate provider evidence into shared runtime state. |

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
