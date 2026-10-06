# Domain 8 — Decision and Execution Boundary

## Purpose

KAORI must not execute a live recommendation payload directly. A recommendation is an observation-derived finding; execution requires an immutable, time-bounded decision snapshot.

## Boundary

The allowed flow is:

```text
Recommendation Finding
  -> DecisionSnapshot
  -> PolicyOutcome
  -> explicit approval when required
  -> signed ExecutionAuthorization
  -> resolver/executor
```

The forbidden flow is:

```text
Recommendation Finding -> resolver/executor
```

## Decision snapshot

`app/intelligence/decision.py` introduces an immutable `DecisionSnapshot` carrying:

- unique decision identity;
- recommendation and base rule identity;
- rule version;
- optional knowledge/runbook version;
- action identity;
- cluster and namespace scope;
- severity;
- canonical copied evidence;
- SHA-256 evidence hash;
- optional inventory generation and alert fingerprint;
- policy outcome and approval requirement;
- creation and expiry timestamps.

The evidence payload is serialized canonically before hashing. Execution can therefore detect drift between the approved evidence and the current evidence.

## Policy

The initial framework-neutral policy produces one of:

- `allowed`;
- `needs_approval`;
- `blocked`.

Maintenance mode, blocked action policy, and missing execution permission fail closed. Critical and warning actions require explicit approval by default.

## Execution token

Execution authorization is HMAC-signed and bound to:

- decision ID;
- action key;
- evidence hash;
- issue time;
- decision expiry;
- nonce.

The authorization validator rejects malformed signatures, mismatched decision/action/evidence, expired decisions, and current evidence drift.

## Deployment

This batch adds no database migration and no route. It establishes the domain contract before persistence, approval UI, RBAC wiring, and resolver adapters are introduced in subsequent batches.

## Rollback

Remove `app/intelligence/decision.py` and its Domain 8 tests/docs. Existing recommendation rendering remains unchanged because no route currently invokes this boundary.
