# Alertmanager Integration Module

## Purpose

This package is the canonical Alertmanager provider module. It owns API v2
transport, endpoint compatibility, alert/silence normalization, capability
validation, evidence, and runtime translation.

## Files

- `adapter.py`: registry operations and shared runtime translation.
- `client.py` and `client_factory.py`: Alertmanager API v2 transport.
- `capabilities.py`: capability keys and compatibility profiles.
- `validation.py`, `probes.py`, `requirements.py`: validation pipeline.
- `alerts.py`, `silences.py`, `reader.py`: read-only provider operations.
- `normalizers/`: provider response normalization.
- `profiles/`: versioned v0.25/v0.33 compatibility contracts.
- `schemas.py`: provider-owned schemas.

## Registry contract

| Operation | Queue | Meaning |
|---|---|---|
| `client.build` | `inline` | Build an API v2 client; no network call. |
| `runtime.validate` | `integration-validation` | Full API/capability validation. |
| `runtime.health` | `integration-runtime` | Lightweight status observation. |
| `runtime.state` | `inline` | Translate evidence into shared runtime state. |

## Persistence and authority

`AlertmanagerInstance` in `app/models/alertmanager.py` stores one reusable
source. `IntegrationBinding` is the only scope-binding table. Alertmanager
remains authoritative for routing, grouping, inhibition, receivers, and
silences; KAORI currently performs read-only provider operations and governed
source resolution.
