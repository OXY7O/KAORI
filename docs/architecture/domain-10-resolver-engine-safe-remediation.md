# Domain 10 — Resolver Engine and Safe Remediation Boundary

## Purpose

Domain 10 introduces a provider-neutral resolver boundary between approved KAORI decisions and future mutation adapters. It does not register a live Kubernetes mutation adapter and therefore does not enable autonomous remediation.

## Mandatory execution sequence

1. Resolve an explicitly registered action adapter.
2. Build a deterministic idempotency key from decision ID, action key, and evidence hash.
3. Execute adapter dry-run.
4. Persist dry-run evidence and rollback metadata.
5. Cancel authorization when dry-run blocks the operation.
6. Consume the signed one-time token only after dry-run succeeds.
7. Execute through the same adapter and immutable resolver context.
8. Persist success, no-op, or failure in the execution journal and Activity Audit Log.

## Guardrails

- Unknown and duplicate action registrations fail closed.
- Resolver input originates from `IntelligenceDecision` and `IntelligenceExecutionJournal`.
- Recommendation payloads cannot be sent directly to an adapter.
- Dry-run is mandatory and precedes token consumption.
- Parameters are exposed as a read-only mapping.
- Idempotency is evidence-bound; changed evidence generates a different key.
- Raw execution tokens are never persisted.
- Provider mutation services are not imported by the shared resolver service.
- Adapter exceptions become terminal failed journal entries; retry automation is intentionally deferred.

## Rollback and compensation metadata

Adapters may return a rollback plan during dry-run and a rollback reference after execution. Domain 10 records these values but does not automatically invoke compensation. Automatic rollback requires provider-specific semantics, ownership checks, and a dedicated policy in a later batch.

## Deployment

No database migration is required. Apply the files, then run focused resolver and Intelligence workflow tests before the full quality gate.

## Rollback

Remove the `app/intelligence/resolver` package and Domain 10 tests/documentation. No database downgrade is necessary. Existing Domain 9 decision and execution journal rows remain valid.
