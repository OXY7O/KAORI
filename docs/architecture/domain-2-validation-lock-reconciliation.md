# Domain 2 — Validation Lock Reconciliation

## Problem

Integration validation uses Redis as a fast cross-process mutex and `JobExecution` as the durable lifecycle record. A worker crash, interrupted dispatch, or prior cleanup could leave a Redis lock alive after its owning canonical job had already become terminal. Until the lock TTL expired, KAORI rejected new validation or runtime refresh work for the same source.

## Decision

Before an atomic validation claim, KAORI now inspects every requested and conflicting Redis lock:

- canonical job status `queued`, `running`, `retrying`, or `cancel_requested`: preserve the lock;
- terminal canonical job: compare-delete the stale lock;
- missing canonical job: compare-delete the orphan lock;
- lifecycle lookup failure: preserve the lock and log the verification failure.

The final claim remains atomic. Reconciliation never deletes a lock whose owner is still active, and compare-delete prevents removing a lock that changed owners during inspection.

## Deployment

No database migration is required. Deploy the web, validation-worker, runtime-worker, and Beat components from the same commit.

## Validation

```bash
pytest -q \
  tests/integrations/test_validation_lock_reconciliation.py \
  tests/contracts/integrations/test_validation_lock_reconciliation_contract.py

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Restore `app/integrations/validation/state.py` and remove the two added tests and this document. Existing lock TTL behavior will return immediately; no stored data requires conversion.

## Changed Files

- `app/integrations/validation/state.py`
- `tests/integrations/test_validation_lock_reconciliation.py`
- `tests/contracts/integrations/test_validation_lock_reconciliation_contract.py`
- `docs/architecture/domain-2-validation-lock-reconciliation.md`
