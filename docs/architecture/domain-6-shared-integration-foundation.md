# Domain 6 — Shared Integration Foundation Stabilization

## Purpose

This stabilization makes canonical lifecycle state authoritative across Kubernetes, Prometheus, and Alertmanager before any runtime is selected or contacted.

## Runtime contract

An integration is operational only when all of the following are true:

- the provider-specific record is enabled;
- the canonical `IntegrationInstance` exists;
- the canonical instance is enabled;
- `lifecycle_status` is exactly `active`.

The shared `ensure_provider_operational()` guard is the reusable worker and synchronous-operation boundary. Provider-specific wrappers may remain for compatibility, but they delegate to this shared implementation.

## Resolver contract

`resolve_integration()` filters canonical rows by both `enabled=True` and `lifecycle_status='active'`. It also performs a defensive lifecycle eligibility check while evaluating candidates. A deleting, inactive, disabled, or unknown lifecycle cannot become the selected source.

## Why this belongs in the shared foundation

Provider-specific guards alone create inconsistent behavior: one integration may fail closed while another still resolves a source in a non-active lifecycle. The canonical resolver and lifecycle service now enforce one rule for every adapter and consumer.

## Deployment

No database migration is required. Apply the patch, run the focused tests, then execute the full integrations and architecture suites.

## Rollback

Revert the production files and tests in the same commit. Existing database records remain compatible because no schema or persisted payload format changes.
