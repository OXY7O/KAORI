# RBAC Security

## 1. Security objectives

KAORI RBAC must:

- deny by default;
- enforce authorization server-side;
- preserve least privilege;
- prevent default-role drift;
- separate Super Admin from ordinary roles;
- prevent silent access loss during role deletion;
- prevent privilege escalation through user or role administration;
- produce auditable role lifecycle records.

## 2. Default deny

A permission check returns false when:

- the user is not Super Admin;
- no active normalized role grants the key;
- no compatible legacy default-role fallback grants the key.

Unknown permission keys are denied for normal users. Super Admin currently returns true for any key, so sensitive new permissions must be reviewed before deployment.

## 3. Route enforcement

Every protected route must use one of:

```python
@permission_required('permission.key')
```

or:

```python
@any_permission_required('permission.one', 'permission.two')
```

Service-level checks remain necessary when authorization depends on target state, actor/target relationship, approval ownership, namespace allow lists, or last-Super-Admin constraints.

## 4. System-role immutability

System role immutability is enforced in multiple layers:

- UI exposes View and Clone, not Edit/Delete;
- edit route rejects system roles;
- delete route rejects system roles;
- `replace_role_permissions()` raises for system roles;
- seed restores canonical metadata and exact permission assignment.

Defense in depth is intentional. UI behavior alone is insufficient.

## 5. Custom-role deletion

Deletion is blocked when the role is referenced by:

- any active, non-deleted user;
- any identity provider as `default_role_id`.

This prevents orphaned user authorization and unsafe JIT fallback behavior. Deactivation should be used before deletion when impact assessment is required.

## 6. Permission dependency integrity

Action permissions automatically include their view prerequisites. This prevents roles that can call a mutation route but cannot load its operational context.

Dependency expansion does not imply broader scope. It only establishes the minimum parent capability needed by the action workflow.

## 7. Privilege escalation boundaries

`roles.manage` can create highly privileged custom roles. Therefore:

- it must remain an administrative permission;
- actors with `roles.manage` must be treated as privilege administrators;
- assigning the new role still requires `users.manage` and User Management actor/target checks;
- a normal Admin must not grant or manage Super Admin authority;
- future scoped roles must prevent a role administrator from granting scope beyond their own delegated boundary.

The current global model does not implement delegated role administration. Any actor with `roles.manage` can define any non-Super-Admin permission combination.

## 8. Sensitive permissions

The following permission families require elevated review:

- protected secret reveal, approval, and policy management;
- Secret create/replace/delete;
- TLS Secret rotation and bulk rotation;
- cluster management;
- integration configuration;
- user lifecycle and password reset;
- role management;
- audit retention execution and archive export;
- report storage cleanup;
- future system management.

Adding a sensitive permission to a broad default role must be an explicit product decision.

## 9. Audit requirements

Role lifecycle actions record:

- actor user;
- action (`role.created`, `role.cloned`, `role.updated`, `role.deleted`);
- target role ID/type;
- summary;
- role slug;
- permission count;
- clone source where applicable;
- active state for updates.

Future improvement: record permission-level before/after diffs and affected user counts.

## 10. Session behavior

Current permission resolution reads the user role relationship on authorization checks and does not persist a permission snapshot in the login session. Role changes and deactivation therefore apply on the next request, subject to SQLAlchemy session loading behavior in the current request.

## 11. CSRF and method safety

Create, clone, edit, and delete flows use Flask-WTF CSRF protection. Deletion is POST-only. Read-only role detail and Permission Catalog are GET operations.

## 12. Fail-safe behavior

- Missing role: return to Roles & Access with a warning/error.
- Unauthorized action: HTTP 403.
- Duplicate role slug: validation error; no database commit.
- Invalid permission ID: ignored by permission lookup rather than inserted as a broken foreign key.
- System-role mutation attempt: reject.
- Delete blocker: reject with assignment/mapping counts.
- Seed rerun: restore default baseline.
