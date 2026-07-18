# RBAC Processes and Flows

## 1. Seed default RBAC

```text
flask seed-rbac
  -> upsert permission registry
  -> upsert five default roles
  -> mark default roles system + active
  -> converge each default role to canonical permission set
  -> backfill missing user.role_id from legacy role slug
  -> commit
```

The command is idempotent and must run after migrations during bootstrap or deployment.

## 2. Authorization request

```text
HTTP request
  -> authentication/session validation
  -> permission_required(key)
  -> current_user.has_permission(key)
       -> Super Admin? allow
       -> active role contains key? allow
       -> legacy default-role fallback contains key? allow
       -> deny
  -> view/service execution OR HTTP 403
```

For routes that accept one of several capabilities, use `any_permission_required()`.

## 3. Create custom role

```text
roles.manage actor opens New Custom Role
  -> enter slug, display name, description, active state
  -> select permissions
  -> validate CSRF and fields
  -> normalize slug
  -> reject duplicate slug
  -> expand permission dependencies
  -> create Role(is_system=false)
  -> create RolePermission rows
  -> record role.created audit event
  -> commit
```

A custom role may be created with minimal permissions, but KAORI administrators should define a clear responsibility and avoid creating user-specific roles.

## 4. Clone default role

```text
roles.manage actor chooses Clone on a default role
  -> load protected source role
  -> prefill custom slug/display name/description
  -> preselect source permissions
  -> administrator narrows or extends permissions
  -> validate as a new custom role
  -> record role.cloned with source metadata
  -> commit independent custom role
```

Only default roles are clone sources in the current UI. The source remains unchanged.

## 5. View role

`roles.view` permits viewing both default and custom role details, including:

- role slug and description;
- system/custom type;
- active state;
- assigned user count;
- effective permissions;
- permission descriptions and keys.

Viewing a role does not grant `roles.manage`.

## 6. Edit custom role

```text
roles.manage actor opens custom role editor
  -> validate role exists and is not system
  -> change metadata/status/permissions
  -> normalize and validate unique slug
  -> expand permission dependencies
  -> replace RolePermission set transactionally
  -> record role.updated audit event
  -> commit
```

An attempt to edit a default role is redirected to read-only detail with guidance to clone.

## 7. Assign role to user

Role assignment is owned by User Management:

```text
users.manage actor edits user
  -> role selector contains active permitted roles
  -> admin-level target/request checks
  -> last-Super-Admin checks where applicable
  -> set users.role_id
  -> maintain legacy role slug compatibility
  -> audit user change
```

A normal Admin cannot assign or modify Admin-level authority unless allowed by the User Management protection rules. Super Admin remains separate from normal role assignment.

## 8. Identity-provider JIT role mapping

```text
provider configuration
  -> select active default_role_id
successful external identity authentication
  -> validate JIT policy
  -> resolve active mapped role
  -> create/update local User projection
  -> set role_id
  -> is_super_admin = false
```

External identity mapping must never grant Super Admin automatically.

## 9. Deactivate custom role

```text
roles.manage actor clears Active Role
  -> save custom role
  -> User.has_permission() stops using that role
  -> role removed from new assignment choices
  -> existing user records remain mapped for review/recovery
```

Deactivation is immediate at the next permission check because current authorization does not cache a permission snapshot in the session.

Before deactivation, administrators should review assigned users to avoid unexpected loss of access.

## 10. Delete custom role

```text
roles.manage actor requests delete
  -> validate CSRF
  -> reject system role
  -> count non-deleted user assignments
  -> count identity-provider default mappings
  -> if blockers exist: reject with details
  -> record role.deleted audit event
  -> delete role and role-permission rows
  -> commit
```

Deletion is permanent. Use deactivation when the role may be needed for recovery, historical review, or temporary suspension.

## 11. Permission registry change

```text
engineer adds permission to app/rbac/defaults.py
  -> add server-side route/service guard
  -> update default-role mapping if required
  -> update navigation visibility
  -> update docs and test matrix
  -> run migration only if schema changes
  -> run flask seed-rbac
  -> verify Permission Catalog and role coverage
```

A permission must not be added only to the UI or only to the default-role seed.
