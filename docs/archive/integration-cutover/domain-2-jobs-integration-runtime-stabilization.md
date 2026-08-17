# Domain 2 — Jobs & Integration Runtime Stabilization

## Scope

This stabilization pass consolidates the Domain 2 patches for Prometheus, Alertmanager, Kubernetes integration runtime, and the shared job lifecycle. It resolves patch overlap between resource admission locking and terminal job finalization, then retains the previously introduced ownership, pagination, stale-lock, dependency, and deletion protections.

## Final behavior

- Disabled Prometheus or Alertmanager sources no longer retain primary binding ownership.
- Runtime observation history returns exactly the requested canonical page size.
- Validation locks are reconciled against durable `JobExecution` state before a new claim.
- Terminal job states are monotonic and cannot be overwritten by late Celery callbacks.
- `cancel_requested` wins completion and failure finalization races.
- Integration deletion detects active dependencies through provider, scope, and canonical resource-group identity.
- Integration deletion and job admission use the same PostgreSQL transaction-scoped advisory lock.
- Admission re-reads the integration target after acquiring the lock and refuses deleted targets.

## Patch-overlap correction

The delete/admission serialization batch also changed `app/jobs/service.py`. Applied after the terminal-state batch, it replaced the terminal finalizer guards. This stabilization pass merges both changes into one source:

- `acquire_resource_admission_locks()` remains active for admission serialization.
- `mark_job_succeeded()`, `mark_job_failed()`, `mark_job_retrying()`, and `mark_job_canceled()` preserve terminal-state monotonicity.

## Deployment

No database migration is required. Deploy application, Celery worker, validation worker, and beat from the same commit so all processes share the same lifecycle contract.

Recommended sequence:

1. Apply the patch.
2. Run the focused functional and contract suites.
3. Run the complete integrations and jobs suites.
4. Run architecture, migration, and quality gates.
5. Restart web and worker processes together.

## Validation

```bash
pytest -q \
  tests/integrations \
  tests/jobs \
  tests/contracts/integrations \
  tests/contracts/jobs

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

## Rollback

Revert the stabilization commit and redeploy all KAORI web and worker processes together. No schema rollback is necessary.

## Changed production files

- `app/alert_sources/providers/alertmanager/service.py`
- `app/cluster/service.py`
- `app/cluster/sync_jobs.py`
- `app/integrations/observability/alert_source/providers/alertmanager/binding_management.py`
- `app/integrations/deletion.py`
- `app/integrations/prometheus/binding_management.py`
- `app/integrations/runtime/repository.py`
- `app/integrations/validation/state.py`
- `app/integrations/validation/web.py`
- `app/jobs/service.py`
- `app/prometheus/service.py`
