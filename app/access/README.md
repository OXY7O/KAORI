# Access Domain

## Purpose

`app/access` owns the administrative Access control-plane presentation and HTTP orchestration for cross-cutting identity and authorization workspaces. It does not own authentication protocols, user persistence, or RBAC policy evaluation.

Canonical landing page:

```text
/access/
```

Current navigation composition:

```text
Access
├── Overview
├── User Management
├── Identity Providers
├── Roles & Access
├── Permission Catalog
└── Activity Audit
```

## Ownership boundary

- `app/access/overview/` owns the read-only Access landing page.
- `app/access/roles/` owns role-management HTTP routes, forms, presentation context, and role mutation orchestration.
- `app/access/permissions/` owns the read-only Permission Catalog HTTP/presentation boundary.
- `app/users/` remains authoritative for user lifecycle, provider administration forms, LDAP directory provisioning, and external identity projection.
- `app/auth/` remains authoritative for Local/LDAP/OIDC/OAuth authentication protocol behavior and session admission.
- `app/rbac/` remains authoritative for the code-owned permission registry, protected default roles, authorization rules, role mutation guardrails, and route decorators.
- `app/notifications/` remains authoritative for Notification Center and Activity Audit persistence/presentation.

The Access menu groups these capabilities; it does not duplicate their domain logic.

## URL ownership

Canonical Access-owned URLs:

```text
/access/
/access/roles/
/access/roles/new
/access/roles/<id>
/access/roles/<id>/clone
/access/roles/<id>/edit
/access/roles/<id>/delete
/access/permissions/
```

User and provider URLs remain canonical under `/users/` until their page-by-page Access review determines whether a URL namespace cutover is useful. The current refactor intentionally avoids changing stable user/provider URLs only for cosmetic consistency.

Legacy Settings role/permission URLs are retired. Settings must not contain redirect shims, compatibility wrappers, or role/permission presentation/mutation logic; callers must use the canonical Access routes.

## UI review boundary

This ownership refactor is an architecture baseline, not the Access UI Final Lock. User Management, Identity Providers, Roles & Access, Permission Catalog, Activity Audit, and Access Overview will be reviewed independently before the Access domain is final-locked.

## Roles & Access review status

Roles & Access now uses the KAORI operational registry pattern: read-only posture overview, compact assignment flow, full-width filtered Role Registry, expandable role evidence, shared pagination/loading, and a sticky impact rail on role forms. The old page-local Role-Permission Mapping Matrix and `role_access_tabs.js` have been removed; cross-role permission coverage belongs to Permission Catalog.

Custom-role edit/delete mutations are serialized with a database row lock and protected by a role version token so stale administrative forms do not silently overwrite a newer role state. Delete blockers for user assignments and Identity Provider defaults are rechecked at mutation time.

This remains a refinement baseline, not the Access Final Lock. RBAC seed/convergence ownership is intentionally deferred to Permission Catalog review.
