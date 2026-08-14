# Alertmanager Integration Module

## Purpose

This package is the canonical Alertmanager provider module. It owns API v2
transport, endpoint compatibility, provider Core Validation, read-only alert and
silence access, runtime translation, and asset-scoped alert consumer validation.

Alertmanager is a reusable alerting provider. It is **not** a Kubernetes-specific
provider. One Alertmanager may receive alerts generated from Kubernetes, MinIO,
infrastructure, applications, and future integrations at the same time.

## Canonical validation boundary

```text
Alertmanager Connection
  → product/version compatibility
  → alertmanager core API capabilities
  → Provider Core Validation
  → Provider Ready

Managed Asset
  → Alertmanager IntegrationBinding
  → Consumer Profile
  → Alert Identity Selector
  → Binding Validation
  → Alert Consumer Eligibility
```

Provider Core Validation checks only provider-owned contracts such as Status,
Alerts, and Silences API v2 access. It must not require active Kubernetes, MinIO,
or other domain alerts.

Binding Validation owns consumer semantics. Current canonical profiles include:

- `kubernetes_cluster` → `kubernetes-alerts-v1`
- `object_storage_system` → `object-storage-alerts-v1`
- `server` → `infrastructure-alerts-v1`
- `server_group` → `infrastructure-group-alerts-v1`
- `hci_environment` → `platform-alerts-v1`
- `storage_service` → `storage-alerts-v1`
- `global` → `global-alerts-v1`

For non-global consumers, the binding selector is mandatory. The selector is the
runtime segregation boundary inside a shared Alertmanager; the Consumer Profile
defines the expected alert payload contract for that asset type. If no alert is
currently active, a valid selector may still be Ready while payload-label
evidence remains unobserved. When representative alerts are active, required
payload evidence is validated and may degrade only that binding.

Alert rules themselves are normally evaluated upstream by Prometheus or another
rule engine. Alertmanager remains authoritative for grouping, inhibition,
routing, silences, and delivery. KAORI consumes the resulting alert stream
through governed bindings; it does not infer Alertmanager provider readiness
from upstream rule presence.

## Files

- `adapter.py`: registry operations and shared runtime translation.
- `client.py` and `client_factory.py`: Alertmanager API v2 transport.
- `capabilities.py`: provider core and consumer-payload capability definitions.
- `binding_profiles.py`: asset-type → alert Consumer Profile registry.
- `binding_management.py`: provider-neutral binding creation and selector invalidation.
- `binding_validation.py`: selector-scoped consumer evidence persisted on `IntegrationBinding`.
- `validation.py`, `probes.py`, `requirements.py`: provider Core Validation pipeline.
- `alerts.py`, `silences.py`, `reader.py`: read-only provider operations.
- `normalizers/`: provider response normalization.
- `profiles/`: versioned v0.25/v0.33 compatibility contracts.
- `contracts.py`: provider-owned result contracts.

## Registry contract

| Operation | Queue | Meaning |
|---|---|---|
| `client.build` | `inline` | Build an API v2 client; no network call. |
| `runtime.validate` | `integration-validation` | Run consumer-neutral provider Core Validation. |
| `runtime.health` | `integration-runtime` | Run a lightweight provider health observation. |
| `runtime.state` | `inline` | Translate provider evidence into shared runtime state. |
| `binding.create` | `inline` | Create a provider-neutral asset binding and resolve its Consumer Profile. |
| `binding.selector.update` | `inline` | Update alert identity and invalidate prior consumer evidence. |
| `binding.validate` | `integration-validation` | Validate the Consumer Profile and selector-scoped alert stream. |

## Source-owned consumer binding UX

Alertmanager is the mutation owner for its alert consumer bindings. `Bindings & Consumers`
uses the shared `Add Binding` modal backed by the canonical managed-asset registry. Current
eligible asset families include Kubernetes clusters and object-storage systems; the asset
type resolves the corresponding alert Consumer Profile and selector contract. Asset-owner
pages only inventory the bound Alertmanager source and do not create/remove the binding.

A future managed asset such as Vault becomes bindable by registering its asset definition
and a compatible alert profile (for example `vault-alerts-v1`); no Vault-specific
Alertmanager form or binding table is required.

## Persistence and authority

`AlertmanagerInstance` in `app/models/alertmanager.py` stores one reusable
connection. `IntegrationBinding` is the only consumer-binding table and persists
`validation_profile`, selector, validation status, and scoped evidence.
Alertmanager remains authoritative for routing, grouping, inhibition, receivers,
and silences. KAORI owns provider registration/readiness, consumer-profile
validation, and governed source resolution.

A failed Kubernetes or MinIO alert binding must not mutate Alertmanager provider
Core Readiness or another consumer binding.

## Canonical application boundary

Provider runtime and binding behavior is implemented in `runtime.py`,
`binding_management.py`, and `binding_validation.py`. The adapter dispatches
every operation directly to those modules. This package must not import
`app.alertmanager`; the web/domain package calls it only through the Integration
Registry.
