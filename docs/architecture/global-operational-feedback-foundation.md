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
- is explicitly marked `activity_audit_saved=False`;
- does not persist a Notification or Activity Audit record.

### Direct Flask flash

New authenticated KAORI application routes must not call Flask `flash()` for operational feedback. Remaining legacy usage is migrated domain by domain. Authentication bootstrap and framework-level fallback behavior must be reviewed separately before removal.

## Notification Center mutation navigation

A non-HTMX notification read-state POST returns to the **server-owned**
`url_for('notifications.center')` route. Only a same-origin, exact Center path
may contribute filter, search or pagination query values, which are parsed
and re-encoded as data. An external, protocol-relative, unrelated internal
route or untrusted referrer falls back to the canonical Center route.
This preserves normal Center context without allowing a request-selected
redirect destination. HTMX page/panel POSTs still return fragments and
their existing notification-change triggers; no notification status or
audit data is changed by the redirect guard.

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
