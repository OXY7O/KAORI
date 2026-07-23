# Authentication Feedback Foundation

## Purpose

Authentication pages use the same KAORI operational toast presentation as authenticated pages while preserving the separate authentication audit trail.

## Contract

- Local login and browser SSO failures queue transient feedback through `queue_transient_feedback()`.
- Authentication failures do not create Notification Center entries.
- Login and logout security evidence continues to be written through `record_authentication_activity()`.
- `layouts/auth.html` consumes one queued quick-action feedback payload and supports dismissing it without HTMX or the authenticated application layout.
- Database setup readiness remains rendered directly as a 503 setup page and clears stale feedback before rendering.

## Security boundary

Usernames, passwords, authorization codes, OAuth state, nonce values, raw provider responses, and exception text are not placed in toast metadata. Existing authentication audit records remain authoritative for success/failure history.

## Rollback

Restore `app/auth/routes.py` and `app/templates/layouts/auth.html`. No database migration or stored-data rollback is required.
