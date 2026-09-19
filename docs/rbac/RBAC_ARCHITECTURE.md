# RBAC Architecture

## 1. Purpose

Authentication proves identity. User Management owns the local KAORI account and identity projection. RBAC resolves the authenticated user into an effective permission set and enforces that set on every protected server-side operation.

The authorization decision is:

```text
authenticated user
  -> active, non-deleted account
  -> explicit Super Admin override OR active assigned role
  -> effective permission keys
  -> route/service authorization decision
```

UI visibility is not an authorization boundary. A hidden menu, disabled button, or omitted link may improve usability, but the route or service must still reject an unauthorized request.

## 2. Component ownership

| Component | Ownership |
|---|---|
| `app/models/rbac.py` | Central SQLAlchemy models for Role, Permission, and RolePermission. |
| `app/models/user.py` | User-to-role relation, role display helpers, and runtime `has_permission()`. |
| `app/access/rbac/defaults.py` | Canonical permission registry and protected default-role definitions. |
| `app/access/rbac/service.py` | Seeding, slug normalization, dependency expansion, permission replacement, and delete blockers. |
| `app/access/rbac/decorators.py` | `permission_required()` and `any_permission_required()` route guards. |
| `app/access/roles/routes.py` / `app/access/permissions/routes.py` | Role and Permission Catalog HTTP lifecycle. |
| `app/access/roles/forms.py` | CSRF-protected role create/update/delete forms. |
| `app/templates/access/roles/` | Roles & Access list, detail, clone, and custom-role editor. |
| `app/templates/access/permissions/` | Read-only permission registry and role coverage. |
| `app/commands/rbac.py` | Idempotent `flask seed-rbac` command. |

All database models remain centralized in `app/models/`. The RBAC domain package contains policy, services, decorators, and documentation only.

## 3. Permission registry

A permission key is a stable application contract with this structure:

```text
<resource-or-domain>.<action>
```

Examples:

- `clusters.view`
- `clusters.sync`
- `jobs.view`
- `jobs.execute`
- `jobs.configure`
- `jobs.cancel`
- `users.reset_password`
- `activity_audit.view`
- `kubernetes_secrets.approve_reveal`

Each permission includes:

- unique key;
- module used for catalog grouping;
- normalized action label;
- human-readable description.

Permission creation and renaming are code changes. They are not administrative UI operations because route guards, navigation, tests, and documentation depend on stable keys.

The administrative ownership boundary is explicit:

- **Permission Catalog** reads the code-owned contract registry and compares it with the persisted database without mutating on GET; `flask seed-rbac` is the explicit synchronization command;
- **Roles & Access** composes permission keys into protected default roles and editable custom roles;
- **User Management** assigns one active role to a local user account;
- **Identity Provider configuration** may map a default role for JIT provisioning;
- **authorization decorators and services** enforce the resulting permission set on the server.

Roles & Access therefore does not directly own user access assignment. It defines the reusable role that User Management or an approved identity-provider mapping can assign.

## 4. Role types

### 4.1 Protected default role

A default role has `is_system = true` and is owned by `DEFAULT_ROLE_DEFINITIONS` and `DEFAULT_ROLE_PERMISSIONS`.

Default roles:

- cannot be edited;
- cannot be deactivated;
- cannot be deleted;
- can be reviewed;
- can be cloned into a custom role;
- are restored to the canonical definition by `seed_default_rbac()`.

The seed is convergent and command-owned. It adds missing default assignments and removes assignments that are not present in the current code baseline. Access HTTP GET routes never invoke the seed implicitly.

### 4.2 Custom role

A custom role has `is_system = false` and may be:

- created from an empty permission selection;
- cloned from a protected default role;
- renamed by display name and slug;
- activated or deactivated;
- assigned a custom permission set;
- deleted only when no non-deleted user or identity-provider default mapping references it.

### 4.3 Super Admin

`User.is_super_admin` is a separate emergency/platform authority flag. It is not a role and does not aggregate with multiple roles.

`User.has_permission()` returns `true` for every key when `is_super_admin` is true. This includes protected permissions intentionally excluded from the Admin default role, such as direct protected secret reveal.

Super Admin lifecycle constraints are enforced by User Management:

- only a Super Admin may manage admin-level accounts;
- the last active Super Admin cannot be demoted, disabled, or deleted;
- normal Admin users cannot manage peer Admin or Super Admin accounts.

## 5. Authorization runtime

`User.has_permission(permission_key)` resolves in this order:

1. Super Admin: allow.
2. Active normalized role record: check `role.permissions`.
3. Legacy role slug fallback: check `DEFAULT_ROLE_PERMISSIONS`.
4. Otherwise: deny.

The legacy fallback exists for migration compatibility. New authorization design must use `role_id` and `role_record` as the normalized source.

## 6. Permission dependencies

KAORI prevents internally inconsistent custom roles by expanding dependent action permissions to include required view permissions.

Examples:

```text
users.manage -> users.view
roles.manage -> roles.view
clusters.sync -> clusters.view + jobs.execute
jobs.execute -> jobs.view
jobs.configure -> jobs.view
jobs.cancel -> jobs.view
reports.generate -> reports.view
kubernetes_configmaps.update -> kubernetes_configmaps.view
settings.export_operational_activity -> activity_audit.view
```

Dependency expansion is performed in `app/access/rbac/service.py` before replacing a custom role's assignments. It is a consistency rule, not a substitute for route guards.


### 6.1 Job orchestration permissions

The Jobs control plane separates lifecycle visibility from manual execution, policy configuration, and cancellation:

- `jobs.view` opens Platform Operations and the execution/configuration workspaces;
- `jobs.execute` permits manual dispatch through a registered job definition;
- `jobs.configure` permits automatic policy changes;
- `jobs.cancel` permits cancellation where the execution type supports it.

A registered job may require an additional owning-domain permission. Kubernetes Inventory Sync requires both `jobs.execute` and `clusters.sync`; the route and dispatcher must not infer domain authority from `jobs.execute` alone. Existing custom roles with `clusters.sync` or `integrations.manage` receive the corresponding job permission during migration.

## 7. Current scope boundary

Current RBAC is global to the KAORI application. A role permission such as `clusters.sync` applies to every cluster visible to the platform. There is no current policy object for:

- selected cluster IDs;
- namespaces;
- environments;
- business services;
- tenants;
- asset ownership;
- time-bound access;
- approval-required role activation.

Future scoped authorization should add a policy layer instead of encoding scope into permission key names.
