# Domain 2 — Job Terminal-State Monotonicity

## Problem

Celery tasks use late acknowledgement and worker-lost redelivery. A delayed completion, failure, or retry callback could therefore update a `JobExecution` after KAORI had already terminalized it as canceled, expired, failed, or succeeded. This could revive terminal work or overwrite the authoritative cancellation/worker-recovery result.

## Contract

- Terminal `JobExecution` states are monotonic and cannot be overwritten by late callbacks.
- `cancel_requested` wins a race against success or failure finalization and becomes `canceled`.
- Retry callbacks cannot revive terminal or cancel-requested jobs.
- Active deduplication ownership is released only through terminalization.

## Deployment

No migration is required. Deploy application and workers together so all lifecycle callbacks use the same transition rules.

## Validation

Run the functional and contract tests listed in `PATCH_MANIFEST.md`, followed by architecture and quality gates.

## Rollback

Revert the service and associated tests/documentation in the same commit. No data rollback is required.

## Changed files

- `app/platform_operations/jobs/service.py`
- `tests/jobs/test_job_terminal_state_monotonicity.py`
- `tests/contracts/jobs/test_job_terminal_state_contract.py`
- `docs/architecture/domain-2-job-terminal-state-monotonicity.md`
