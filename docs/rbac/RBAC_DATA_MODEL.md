# RBAC Data Model

## 1. Entity relationship

```text
Role 1 ---- * RolePermission * ---- 1 Permission
  |
  +---- * User
  |
  +---- * IdentityProvider.default_role_id
```

A user has at most one normalized role. A role has many permissions through the explicit `role_permissions` association model.

## 2. `roles`

| Field | Meaning |
|---|---|
| `id` | Internal primary key. |
| `name` | Stable unique role slug. |
| `display_name` | Human-readable label. |
| `description` | Responsibility and access-boundary description. |
| `is_system` | Marks code-owned protected default roles. |
| `is_active` | Controls whether role-derived permissions are effective and whether the role is available for new assignments. |
| `created_at` | Creation timestamp. |
| `updated_at` | Last update timestamp. |

### Invariants

- `name` is unique.
- System roles are always active after seeding.
- System role identity and permission assignments are immutable through HTTP routes.
- Custom role slugs are normalized to lowercase underscore format.
- Inactive roles do not grant permissions through `User.has_permission()`.

## 3. `permissions`

| Field | Meaning |
|---|---|
| `id` | Internal primary key. |
| `key` | Stable unique authorization contract. |
| `module` | Permission Catalog grouping. |
| `action` | Humanized action and matrix classification. |
| `description` | Operational capability description. |
| `created_at` | Registry creation timestamp. |

Permission keys must not be treated as user-editable data. Code, tests, route decorators, navigation, and documentation depend on them.

## 4. `role_permissions`

| Field | Meaning |
|---|---|
| `id` | Internal primary key. |
| `role_id` | Role foreign key with cascade delete. |
| `permission_id` | Permission foreign key with cascade delete. |
| `created_at` | Assignment timestamp. |

The unique constraint `uq_role_permission(role_id, permission_id)` prevents duplicate assignments.

## 5. `users.role_id`

`users.role_id` is the normalized assignment and uses `ON DELETE SET NULL`.

KAORI does not rely on that database behavior as the role deletion workflow. The application blocks custom-role deletion while non-deleted users still reference the role. This prevents silent access loss and orphaned user authorization state.

`users.role_id` is the only persisted role authority. The retired `users.role` slug is removed by the foundation cleanup migration.

## 6. `users.is_super_admin`

`is_super_admin` is an explicit override outside the role table. It must not be represented by a `super_admin` role because the application applies stricter lifecycle and authentication controls to this authority.

## 7. Identity-provider default mapping

`identity_providers.default_role_id` maps a successful JIT identity projection to one active KAORI role.

A custom role cannot be deleted while referenced by an identity provider. Deleting it would otherwise set the mapping to null and break future JIT provisioning or create an unsafe fallback decision.

## 8. Recommended future extensions

Do not overload the current tables for resource scope. Introduce explicit policy entities when scoped access is implemented, for example:

```text
RoleScope
- role_id
- scope_type      # cluster, namespace, environment, service, asset_group
- scope_reference
- effect          # allow/deny if deny semantics are introduced
- valid_from
- valid_until
```

Multi-role assignment, if introduced, should use a dedicated `user_roles` association and a documented conflict strategy. It must not be implemented by overloading `users.role_id` or encoding multiple role values in one field.
