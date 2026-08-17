# KAORI Operational Feedback Coverage Audit — 2026-08-08

Status: **PASS**

2026-08-17 extension: Reports mutation coverage and notification-surface style checks were added to the same release gate.

This audit verifies operator-facing mutation feedback across the requested KAORI domains. The canonical event is persisted once through `record_operational_activity()` and is then exposed according to the delivery policy as immediate toast feedback, the user-scoped Notification Center, and the administrative Activity Audit.

## Coverage Result

| Category | Audited mutation surfaces | Immediate feedback | Notification Center | Activity Audit | Result |
| --- | --- | --- | --- | --- | --- |
| ConfigMap Management | Create, update, delete, validation and failure paths | Yes | Destructive/failure only; routine create/update success stays out of the inbox | Yes | PASS |
| TLS Certificate | Rotation, bulk rotation, inventory synchronization dispatch/result and failure paths | Yes / Activity Center for running work | Persistent terminal/attention evidence | Yes | PASS |
| Secret Management | Create, replace, delete, protected reveal request/approval/deny/reveal/failure | Yes | Delete/security-attention outcomes only; routine create/replace and reveal value remain out of inbox | Yes | PASS |
| Integrations | Kubernetes connection, Metrics Source instance/binding, Alertmanager instance/binding create/update/delete plus validation/runtime dispatch | Yes / Activity Center for running work | CRUD and persistent terminal outcomes | Yes | PASS |
| Reports | Generate/queue, template CRUD/duplicate, schedule CRUD/toggle/run, storage verification, generated-report archive/restore | Yes / Activity Center for running generation | By delivery policy; failures and selected terminal outcomes may persist | Yes | PASS |
| Platform Operations | Job policy/manual dispatch/cancellation, Data Lifecycle policy/execution, Secret Reveal readiness/policy | Yes / Activity Center for running work | Persistent policy/security/terminal outcomes | Yes | PASS |
| Access | Users, account lifecycle, Identity Provider create/update/validation, external identity provisioning, RBAC role mutation | Yes | Yes for security-significant persisted outcomes | Yes | PASS |
| Settings | Account security and personal time/locale preference mutations | Yes | Account security only; routine personal preference stays out of inbox | Yes | PASS |

## Delivery Decisions

Routine success is deliberately not synonymous with a Notification Center row. KAORI avoids inbox noise while retaining durable administrative evidence:

- ConfigMap create/update success uses **Toast + Activity Audit**; delete and failures are persistent.
- Secret create/replace success uses **Toast + Activity Audit**; delete, approval decisions, and failures are persistent.
- One-time Secret reveal completion is **Audit-only persistence + Toast**; revealed values are never written to Notification Center or Activity Audit metadata.
- Settings time-zone and regional-format changes use **Toast + Activity Audit** and do not refresh the Notification Center because no deck-visible record was created.
- Background work reports progress through **Activity Center / Jobs & Executions** rather than repeated progress toasts.

## Category Verification

Notification Center category presentation is normalized in `app/notifications/event_catalog.py` without changing stored event keys. The audited categories are:

- ConfigMap Management
- TLS Certificate
- Secret Management
- Integrations
- Reports
- Platform Operations
- Access
- Settings

## Title and Evidence Verification

Notification titles are normalized through `standardize_activity_title()` before persistence and again during presentation for historical records. Operational acronyms such as KAORI, K8s, ConfigMap, TLS, RBAC, LDAP, OIDC, SSO, SAML, API, URL, and S3 retain their canonical casing.

Message and detail fields remain sentence-style operational copy; they are intentionally not converted to Title Case.

## Security Boundary

The audit confirms that the feedback contract must never include Secret values, passwords, kubeconfigs, tokens, private keys, or raw credentials. Validation-only feedback may be transient and therefore may intentionally have no durable Activity Audit / Notification Center record.

## Release Gate

The coverage is release-gated by:

- `scripts/verify_operational_feedback_coverage.py`
- `tests/contracts/notifications/test_operational_feedback_coverage_contract.py`
- `scripts/quality_gate.sh`

Any future CRUD/mutation surface in these categories must use the same operational feedback boundary or update the locked delivery matrix with an explicit rationale.
