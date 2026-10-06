# RBAC domain

RBAC is KAORI's authorization layer. It defines the code-owned permission registry, protected default roles, custom-role consistency rules, and reusable route guards.

Database models remain centralized in `app/models/`; role-management and Permission Catalog HTTP/presentation ownership lives in `app/access/`.

## File responsibilities

### `__init__.py`

Package marker. It must not contain policy or import-time database work.

### `defaults.py`

Canonical registry for:

- permission key, module, action, and description;
- five protected default-role definitions;
- exact permission set for Viewer, Operator, Editor, Admin, and Auditor;
- permission dependency graph;
- capability-based Access administration boundary used to classify administrator-level roles.

A permission added here must also be enforced in code, represented in navigation where applicable, documented, seeded, and tested.

### `decorators.py`

Provides:

- `permission_required(permission_key)`;
- `any_permission_required(*permission_keys)`.

Both require authentication and return HTTP 403 when authorization fails. Do not replace server-side decorators with template-only visibility checks.

### `notifications.py`

Builds the standard persistent KAORI toast and Notification-backed Activity Audit metadata for role create, clone, update, failure, blocked delete, and delete outcomes. It does not replace the successful-mutation `AuditEvent` record.

### `service.py`

Owns RBAC business rules:

- idempotent and convergent default seeding;
- role slug normalization and uniqueness lookup;
- active-role query;
- Permission Catalog module grouping;
- source-controlled permission dependency expansion;
- safe replacement of custom-role permissions;
- protected-default and unexpected-system-role mutation rejection;
- custom-role delegation boundarys so non-break-glass administrators cannot grant permissions they do not possess;
- custom-role deletion blockers for users and identity providers.

## Related files

- `app/models/rbac.py`: Role, Permission, RolePermission.
- `app/models/user.py`: normalized role relation and `has_permission()`.
- `app/access/roles/routes.py`: role list/detail/create/clone/edit/delete HTTP orchestration.
- `app/access/roles/forms.py`: role and deletion CSRF forms.
- `app/access/roles/service.py`: role create/clone mutation orchestration.
- `app/access/roles/presentation.py`: role list/form presentation context.
- `app/templates/access/roles/`: Roles & Access list and role form.
- `app/static/js/role_permission_editor.js`: scoped Permission Matrix search, module toggles, global Select all/Clear all, counters, and viewport protection.
- `app/access/permissions/`: read-only Permission Catalog HTTP/presentation boundary.
- `app/templates/access/permissions/`: read-only Permission Catalog template.
- `app/commands/rbac.py`: `flask seed-rbac`.
- `docs/rbac/`: complete architecture, data model, flow, default-role review, permission-registry review, security, UI, and test documentation.

## Non-negotiable rules

- Default roles cannot be edited, deactivated, or deleted.
- Clone a default role when a different permission set is required.
- Custom-role deletion is blocked while referenced by users or identity-provider defaults.
- Super Admin remains a Local Database-only emergency authority flag.
- A custom role slug can never reuse a source-controlled protected default key, even when the database baseline is missing or drifted.
- Administrator-level role classification is capability-based from `access_administration_permissions`, never inferred from the role slug `admin`.
- Deactivating a referenced custom role requires explicit impact acknowledgement because assigned users fail closed and Identity Provider default mappings become unusable.
- UI visibility is not authorization.
- Every protected mutation requires a server-side permission guard and target-state validation.
- Current role scope is global; do not imply cluster- or namespace-scoped RBAC.


## Operational feedback rule

RBAC routes do not use Flask flash messages. Mutation outcomes are recorded through `role_access_feedback()`, which produces both the standard persistent toast and the Activity Audit notification record. Successful mutations continue to write `AuditEvent` rows before the primary transaction commits.

## RBAC convergence boundary

`seed_default_rbac()` is a governed command/bootstrap operation, not an HTTP read-path side effect. Access pages must never call it from GET routes or presentation builders. Permission Catalog compares `DEFAULT_PERMISSIONS` with the persisted registry and reports drift without mutating it. Roles & Access separately compares protected default-role identity, lifecycle, metadata, and permission membership against `DEFAULT_ROLE_DEFINITIONS` / `DEFAULT_ROLE_PERMISSIONS`; drift remains protected from UI mutation until explicit RBAC convergence.

`flask seed-rbac` may create missing canonical permissions, synchronize canonical metadata, converge protected default roles, and normalize default-role mappings. Database-only permission rows are not silently deleted by Permission Catalog; operators must review role usage before any controlled cleanup migration.

Fresh installation runs the Alembic migration chain before `seed-rbac` or `bootstrap-admin`. RBAC data migrations must therefore tolerate an unseeded database when no persisted roles exist, while still failing closed if a legacy permission required to preserve role assignments is missing from an already-seeded RBAC state. Migration code must never require the post-migration seed command to have run first.

## Object Storage domain split

Object Storage visibility does not inherit the Kubernetes read permissions. Canonical read contracts are:

- `inventory.view` — Kubernetes Inventory only;
- `object_storage_inventory.view` — committed Object Storage Inventory;
- `analytics.view` — Kubernetes Analytics only;
- `object_storage_analytics.view` — Object Storage Analytics.

`storage.sync` depends on `object_storage_inventory.view` and `jobs.execute`. The 2026-08-14 RBAC split migration preserves existing role access by copying legacy `inventory.view` and `analytics.view` role assignments to the new Object Storage permissions before routes begin enforcing them.
