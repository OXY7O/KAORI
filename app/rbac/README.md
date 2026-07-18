# RBAC domain

RBAC is KAORI's authorization layer. It defines the code-owned permission registry, protected default roles, custom-role consistency rules, and reusable route guards.

Database models remain centralized in `app/models/`; role-management HTTP routes remain in `app/settings/`.

## File responsibilities

### `__init__.py`

Package marker. It must not contain policy or import-time database work.

### `defaults.py`

Canonical registry for:

- permission key, module, action, and description;
- five protected default-role definitions;
- exact permission set for Viewer, Operator, Editor, Admin, and Auditor.

A permission added here must also be enforced in code, represented in navigation where applicable, documented, seeded, and tested.

### `decorators.py`

Provides:

- `permission_required(permission_key)`;
- `any_permission_required(*permission_keys)`.

Both require authentication and return HTTP 403 when authorization fails. Do not replace server-side decorators with template-only visibility checks.

### `service.py`

Owns RBAC business rules:

- idempotent and convergent default seeding;
- role slug normalization and uniqueness lookup;
- active-role query;
- Permission Catalog module grouping;
- action-to-view permission dependency expansion;
- safe replacement of custom-role permissions;
- system-role mutation rejection;
- custom-role deletion blockers for users and identity providers.

## Related files

- `app/models/rbac.py`: Role, Permission, RolePermission.
- `app/models/user.py`: normalized role relation and `has_permission()`.
- `app/settings/routes.py`: list/detail/create/clone/edit/delete and Permission Catalog routes.
- `app/settings/roles/forms.py`: role and deletion CSRF forms.
- `app/templates/settings/roles/`: KAORI Violet role registry and role form.
- `app/templates/settings/permissions/`: read-only Permission Catalog.
- `app/commands/rbac.py`: `flask seed-rbac`.
- `docs/rbac/`: complete architecture, data model, flow, default-role review, permission-registry review, security, UI, and test documentation.

## Non-negotiable rules

- Default roles cannot be edited, deactivated, or deleted.
- Clone a default role when a different permission set is required.
- Custom-role deletion is blocked while referenced by users or identity-provider defaults.
- Super Admin remains a separate emergency authority flag.
- UI visibility is not authorization.
- Every protected mutation requires a server-side permission guard and target-state validation.
- Current role scope is global; do not imply cluster- or namespace-scoped RBAC.
