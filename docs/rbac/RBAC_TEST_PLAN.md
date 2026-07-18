# RBAC Test Plan

## 1. Test objectives

Tests must prove that UI visibility and server-side enforcement remain aligned, default roles cannot drift, custom-role lifecycle is safe, and sensitive permissions are not accidentally broadened.

## 2. Unit tests

### Role slug normalization

- spaces become underscores;
- hyphens become underscores;
- uppercase becomes lowercase;
- repeated separators collapse;
- unsupported characters are removed/replaced;
- empty or one-character result is rejected;
- duplicate normalized slug is rejected.

### Permission dependency expansion

Test at least:

- `users.manage` adds `users.view`;
- `roles.manage` adds `roles.view`;
- `clusters.sync` adds `clusters.view`;
- `reports.generate` adds `reports.view`;
- ConfigMap/Secret/TLS mutations add corresponding view permissions;
- audit export/retention adds operational activity view;
- recursive expansion is stable and idempotent;
- unknown IDs do not create broken associations.

### `User.has_permission()`

- Super Admin allows registered sensitive permission;
- active role grants assigned permission;
- active role denies unassigned permission;
- inactive role denies all role permissions;
- legacy default-role fallback remains compatible;
- unknown permission denied for normal user.

## 3. Seed tests

- creates all registered permissions;
- creates exactly five protected default roles;
- sets every default role active/system;
- adds missing canonical assignments;
- removes extra assignment from a default role;
- updates changed permission metadata;
- updates changed default-role metadata;
- preserves custom role metadata and custom assignments;
- backfills missing `role_id` from a valid legacy role;
- falls back unknown legacy role to Viewer;
- second run is idempotent.

## 4. Route authorization tests

For each role-management endpoint:

| Endpoint | Required permission | Expected behavior |
|---|---|---|
| `GET /settings/roles` | `roles.view` | 200 or 403. |
| `GET /settings/permissions` | `roles.view` | 200 or 403. |
| `GET /settings/roles/<id>` | `roles.view` | Read-only detail. |
| `GET/POST /settings/roles/new` | `roles.manage` | Create or 403. |
| `GET/POST /settings/roles/<id>/clone` | `roles.manage` | Clone default only. |
| `GET/POST /settings/roles/<id>/edit` | `roles.manage` | Edit custom only. |
| `POST /settings/roles/<id>/delete` | `roles.manage` | Delete safe custom role only. |

Test direct HTTP calls, not only hidden links.

## 5. Lifecycle integration tests

### Create

- valid custom role persists;
- duplicate slug returns validation error;
- selected permissions persist;
- dependencies are added;
- audit event is written.

### Clone

- only system role accepted as source;
- source metadata is prefilled;
- source permissions are selected;
- source role remains unchanged;
- cloned role is custom and independent;
- audit event contains source role.

### Edit

- custom metadata and permissions update;
- system role edit is rejected;
- inactive custom role stops granting permissions;
- audit event includes state and permission count.

### Delete

- system role deletion rejected;
- assigned-user blocker rejected;
- identity-provider mapping blocker rejected;
- unreferenced custom role deleted;
- role-permission rows cascade;
- audit event remains queryable after target deletion;
- invalid/missing CSRF rejected.

## 6. Default-role regression matrix

Assert the exact permission key set for Viewer, Operator, Editor, Admin, and Auditor. A permission change must produce an intentional test update.

Critical assertions:

- Admin does not have `kubernetes_secrets.reveal`;
- Auditor has no mutation permission;
- Viewer has no mutation permission;
- Operator has no cluster management/delete or generic Secret delete;
- Editor has no user/role administration;
- only Admin baseline contains `roles.manage` and user lifecycle mutations.

## 7. User assignment tests

- inactive roles excluded from new assignment choices;
- normal Admin cannot assign Admin-level target authority when blocked by User Management policy;
- Super Admin can manage allowed admin-level assignment;
- last active Super Admin cannot be demoted;
- external JIT assignment never sets `is_super_admin`;
- identity provider rejects missing/inactive default role.

## 8. UI tests

Validate light and dark mode at 1366×768, 1440×900, and 1920×1080.

Roles & Access:

- shared KAORI hero alignment;
- default pagination 5 with 5/10/25/50 choices;
- search/type/status filters reset page;
- Viewer with `roles.view` does not see management actions;
- default role shows View and Clone only;
- custom role shows View/Edit/Delete according to permission and blockers;
- delete modal is keyboard dismissible;
- empty/search state is readable;
- long descriptions and permission lists do not break layout.

Role form:

- default role fields and permissions are visibly read-only;
- clone source is explicit;
- selected permission count updates;
- module select/clear works;
- validation errors retain selected permissions;
- focus rings and keyboard interaction are visible.

Permission Catalog:

- read-only policy is explicit;
- module filter, search, collapse, and role links work;
- permission key remains monospace and readable;
- unassigned permission state is distinct.

## 9. Static verification

Add CI checks that compare:

- permission keys referenced by decorators/templates/services;
- keys defined in `DEFAULT_PERMISSIONS`;
- keys assigned by `DEFAULT_ROLE_PERMISSIONS`.

The build must fail when code references an unregistered permission key.

## 10. Implemented automated coverage

`tests/rbac/test_role_service.py` currently verifies:

- exact default-role convergence after a missing and an extra assignment are introduced;
- automatic action-to-view permission dependencies for custom roles;
- rejection of permission replacement on protected system roles;
- user and identity-provider delete blockers;
- deterministic role-slug normalization.

The remaining route, account-assignment, audit-event, and browser-level cases in this document are the next test increments.
