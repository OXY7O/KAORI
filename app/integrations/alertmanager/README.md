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
| `runtime.validate` | `integration-validation` | Run full API, compatibility, and capability validation. |
| `runtime.health` | `integration-runtime` | Run a lightweight status endpoint observation. |
| `runtime.state` | `inline` | Translate provider evidence into shared runtime state. |
| `binding.create` | `inline` | Create a provider-neutral operational-scope binding. |
| `binding.selector.update` | `inline` | Update the alert selector and invalidate prior binding evidence. |
| `binding.validate` | `integration-validation` | Validate the scoped Alertmanager filter against active alerts. |

## Persistence and authority

`AlertmanagerInstance` in `app/models/alertmanager.py` stores one reusable
source. `IntegrationBinding` is the only scope-binding table. Alertmanager
remains authoritative for routing, grouping, inhibition, receivers, and
silences; KAORI currently performs read-only provider operations and governed
source resolution.

## Canonical application boundary

Provider runtime and binding behavior is implemented in `runtime.py`,
`binding_management.py`, and `binding_validation.py`. The adapter dispatches
every operation directly to those modules. This package must not import
`app.alertmanager`; the web/domain package calls it only through the Integration
Registry.
