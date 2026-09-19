# KAORI Role-Based Access Control

This directory is the technical documentation set for KAORI role and permission management. It continues the authentication and user-management documentation with the authorization layer that determines what an authenticated identity may do.

## Documents

| Document | Purpose |
|---|---|
| `RBAC_ARCHITECTURE.md` | Authorization boundaries, components, ownership, and runtime decisions. |
| `RBAC_DATA_MODEL.md` | Role, permission, assignment, user, and identity-provider relationships. |
| `RBAC_FLOWS.md` | Default seeding, create, clone, edit, assignment, authorization, deactivate, and delete flows. |
| `DEFAULT_ROLE_REVIEW.md` | Review of Viewer, Operator, Editor, Admin, Auditor, and Super Admin authority. |
| `PERMISSION_REGISTRY_REVIEW.md` | Review of active, baseline, reserved, and legacy permission contracts. |
| `RBAC_SECURITY.md` | Least privilege, system-role immutability, privilege escalation controls, audit, and failure behavior. |
| `RBAC_TEST_PLAN.md` | Required unit, integration, authorization, lifecycle, and UI tests. |
| `ROLE_ACCESS_UI.md` | KAORI Violet design and interaction contract for Roles & Access and Permission Catalog. |

## Scope

KAORI currently implements global application RBAC with these properties:

- one normalized role assignment per user;
- code-owned permission registry;
- five protected default roles;
- editable custom roles;
- explicit `is_super_admin` emergency authority outside normal role aggregation;
- route-level server-side permission enforcement;
- read-only Permission Catalog;
- audit records for custom-role lifecycle changes;
- identity-provider default role mapping for JIT provisioning.

Cluster-, namespace-, environment-, tenant-, and resource-level authorization scopes are not implemented yet. They are future policy dimensions and must not be implied by the current UI.
