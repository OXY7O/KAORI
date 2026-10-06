# Domain 11 — Distributed Execution Orchestration Safety

## Purpose

Domain 11 makes resolver execution safe across multiple Celery workers without creating a second job authority. `JobExecution` remains KAORI's canonical Celery delivery record. `IntelligenceExecutionJournal` remains the authorization, lease, retry, and remediation-result authority.

## Execution flow

```text
Authorized execution journal
→ prepare canonical delivery and idempotency key
→ resolver-execution queue
→ acquire database lease using row lock
→ execute Domain 10 dry-run and guarded resolver
→ complete orchestration or classify failure
→ retry_wait or dead_letter
```

## Queue isolation

Mutation work must use `resolver-execution`. Lease reconciliation uses `resolver-maintenance`. Resolver workloads must not share the validation, inventory synchronization, analytics, or forecasting queues.

## Distributed lease

A worker may execute only after persisting `lease_owner`, `lease_acquired_at`, `lease_expires_at`, and `last_heartbeat_at`. Acquisition locks the journal row. A second worker fails closed while the first lease remains active.

## Deduplication

The persisted idempotency key is derived from decision ID, action key, and evidence hash. A unique database constraint prevents duplicate active delivery across web processes, workers, and replicas.

## Retry policy

Failures are classified as retryable, timeout, worker_lost, or terminal. Retryable failures use bounded exponential backoff and never exceed `max_attempts`. Terminal failures or exhausted retries enter `dead_letter` and require explicit operational review.

## Stale recovery

The maintenance task scans expired running leases with `FOR UPDATE SKIP LOCKED`. It returns eligible journals to `retry_wait`; exhausted journals move to `dead_letter`. Recovery creates Activity Audit evidence.

## Deployment

1. Stop resolver workers and Beat.
2. Apply the migration.
3. Configure dedicated workers for `resolver-execution` and `resolver-maintenance`.
4. Start workers before enabling any resolver dispatch route.
5. Schedule stale lease reconciliation at a cadence shorter than the operational recovery objective.

Example worker separation:

```bash
celery -A app.extensions.celery worker -Q resolver-execution --concurrency=2
celery -A app.extensions.celery worker -Q resolver-maintenance --concurrency=1
```

## Validation

```bash
flask db heads
flask db upgrade
pytest -q tests/resolver/test_distributed_orchestration.py tests/contracts/resolver/test_domain11_orchestration_contract.py
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Stop resolver queues before downgrade. Confirm no journal is `running`, `queued`, or `retry_wait`. Export execution and audit evidence, then downgrade to `20260723_decision_workflow`. Downgrade removes orchestration lease and retry metadata; it does not remove Domain 9 decision and authorization records.
