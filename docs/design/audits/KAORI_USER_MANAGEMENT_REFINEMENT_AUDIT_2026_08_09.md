# KAORI User Management Refinement Audit — 2026-08-09

## Scope

User Management under the Access control plane. This audit covers account lifecycle correctness, super-admin safety, User Directory presentation, HTMX feedback, shared KAORI UI ownership, and audit/session boundaries. It is **not** the User Management Final Lock.

## Correctness decisions

### Restore is inactive

Restore now clears the soft-delete marker and leaves the account inactive. Activation remains a separate explicit administrator decision.

### Last active super admin is serialized

Presentation checks remain lock-free. Deactivate, delete, and edit paths that can remove active super-admin authority acquire a row lock across the active super-admin set and then re-run the final guardrail check inside that transaction.

### Audit ledger remains dual-write temporarily

`AuditEvent` still has active consumers outside User Management. User Management therefore keeps the legacy primary-transaction event and the Notification-backed operational feedback until a cross-domain audit-ledger migration is designed.


### Reset Password and right-rail standard

- Reset Password now uses the same shared `page_hero.context_card(...)` grammar as Inventory and User Management instead of a page-local hero panel.
- Reset Impact is a neutral operational evidence card covering password hash, preserved account/role state, Activity Audit evidence, and the currently open authenticated-session boundary.
- The secure-delivery helper is compact: `Share the new password securely; administrator resets are not temporary.`
- Access main-content right rails use one desktop contract: `xl:sticky xl:top-5`. Hero context panels are excluded because they remain part of the hero component rather than the scrolling content rail.

### Password reset session invalidation remains open

Inactive/deleted users are rejected by the Flask-Login user loader. Password reset does not yet version-invalidate already authenticated sessions. This remains an explicit security follow-up before User Management Final Lock.

## UI refinement

- User Management hero now uses the same `page_hero.context_card()` contract as Kubernetes Inventory: posture status, two operational metrics, and one contextual action.
- Hero Add User action is permission-aware; Directory Provisioning moved to Identity Sources context.
- Account & Identity Posture now mirrors the Permission Registry Overview grammar: four lifecycle metrics followed by four identity/lifecycle boundary cards.
- User Directory uses shared loading bar and table/filter primitives; desktop filters stay on one responsive row from the `lg` breakpoint.
- Role filter includes inactive roles with an explicit inactive label.
- Main register actions are reduced to Edit and View Details.
- Expand-below details own Authentication, Authorization, Lifecycle, and administrative actions.
- Delete uses the shared destructive-confirmation component.
- Pagination uses Title Case resource naming, visible `Rows`, and Previous / numeric / Next navigation.

## Open before Final Lock

1. Decide and implement password-reset session-generation invalidation if required by the Access security standard.
2. Review Add/Edit User form UI independently.
3. Complete Identity Providers, Roles & Access, Permission Catalog, and Activity Audit reviews.
4. Run full Access final-lock audit only after all child workspaces are accepted.
