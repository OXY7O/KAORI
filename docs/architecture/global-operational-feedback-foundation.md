# Global Operational Feedback Foundation

## Purpose

KAORI uses one operational feedback contract for full-page redirects and HTMX responses. Domain routes must not choose independently between Flask `flash()`, inline banners, and operational toasts.

## Contracts

### Persistent operational activity

Use `record_operational_activity()` for a mutation, execution, verification, or lifecycle action that must be visible in Activity Audit Log. The feedback payload is queued with `queue_feedback=True` when the response redirects.

Required metadata must be operationally useful and safe. Secrets, credentials, kubeconfig content, report contents, and raw provider payloads must never be included.

### Transient feedback

Use `queue_transient_feedback()` for validation feedback, read-only failures, or navigation outcomes that do not represent an auditable operation. Transient feedback:

- uses the standard KAORI operational toast;
- survives one normal redirect or render;
- is explicitly marked `notification_saved=False`;
- does not persist a Notification or Activity Audit record.

### Direct Flask flash

New authenticated KAORI application routes must not call Flask `flash()` for operational feedback. Remaining legacy usage is migrated domain by domain. Authentication bootstrap and framework-level fallback behavior must be reviewed separately before removal.

## Reports migration

The first migration covers:

- report request creation;
- report PDF generation and regeneration failure;
- report download unavailability;
- active report storage verification.

Report form validation and download availability errors are transient. Report creation, PDF generation, and storage verification are persisted operational activities.

## Validation and rollback

Run:

```bash
pytest -q \
  tests/notifications/test_transient_feedback.py \
  tests/contracts/notifications/test_operational_feedback_contract.py

python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

Rollback by reverting the Part 2 commit. No database migration is required.
