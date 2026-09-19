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
- `app/access/activity_audit/` owns the system-wide Activity Audit HTTP/workspace boundary.
- `app/access/users/` remains authoritative for user lifecycle and effective-access presentation.
- `app/access/identity_providers/` owns Identity Provider administration and directory projection workflows.
- `app/access/authentication/identity_provider/` owns provider catalog, adapter registries, protocol validation, and external authentication contracts.
- `app/access/authentication/` owns session admission and authentication orchestration.
- `app/access/rbac/` remains authoritative for the code-owned permission registry, protected default roles, authorization rules, role mutation guardrails, and route decorators.
- `app/platform_operations/notifications/` remains authoritative for Notification Center persistence and the shared operational evidence store/query kernel. Activity Audit presentation and HTTP orchestration belong to `app/access/activity_audit/`.

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
/access/activity-audit/
/access/activity-audit/<notification-id>/details
```

User lifecycle remains under `/users/`. Identity Provider administration is canonical under `/access/identity-providers/`; no compatibility route is retained under `/users/providers`.

Legacy Settings role/permission URLs are retired. Settings must not contain redirect shims, compatibility wrappers, or role/permission presentation/mutation logic; callers must use the canonical Access routes.

## Final lock boundary

Access v1 is final-locked across Access Overview, User Management, Identity Providers, Roles & Access, Permission Catalog, and Activity Audit. Runtime ownership remains distributed by domain, while the Access control-plane UI, security boundaries, canonical components, and legacy-cleanup rules are protected by `scripts/verify_access_final_lock.py`.

## Access Overview review status

Access Overview is a read-only composition surface. It does not query User, Identity Provider, Role, Permission, or Activity persistence directly to invent a second health model. The overview consumes domain-owned summary contracts and only aggregates permission-scoped posture.

The posture contract now treats missing active break-glass authority, active users without role assignment, inactive roles with assigned users, permission-registry drift and enabled identity-provider configuration/admission-policy gaps as explicit review signals. Activity Audit warning/error records remain evidence counts and do not make the audit workspace itself unhealthy. Optional external authentication remains informational when no provider is configured.

Control Boundaries expose the same authoritative posture as their source workspace instead of static architecture copy alone. This composition rule is protected by `scripts/verify_access_final_lock.py`.

## Roles & Access review status

Roles & Access now uses the KAORI operational registry pattern: read-only posture overview, compact assignment flow, full-width filtered Role Registry, expandable role evidence, shared pagination/loading, and a sticky impact rail on role forms. The old page-local Role-Permission Mapping Matrix and `role_access_tabs.js` have been removed; cross-role permission coverage belongs to Permission Catalog.

Custom-role edit/delete mutations are serialized with a database row lock and protected by a role version token so stale administrative forms do not silently overwrite a newer role state. Delete blockers for user assignments and Identity Provider defaults are rechecked at mutation time.

The role mutation boundary also enforces a delegation boundary: a non-break-glass role manager can only grant permissions already present in their own effective role. Protected default keys remain source-controlled even if database `is_system` metadata drifts, and Roles & Access surfaces baseline drift until explicit `flask seed-rbac` convergence. Administrator-level role classification is capability-based from the RBAC catalog rather than the role slug. Deactivating a referenced custom role requires explicit impact acknowledgement.

This Roles & Access presentation is part of Access Final Lock v1. RBAC seed/convergence remains an explicit deployment boundary owned by the Permission Catalog and `flask seed-rbac`.

## Permission Catalog review status

Permission Catalog is a read-only Access workspace. HTTP GET routes no longer call `seed_default_rbac()` or perform RBAC convergence. Code-to-database alignment is presented as registry evidence (`Canonical`, `Missing From Registry`, `Metadata Drift`, or `Database Only`), while synchronization remains an explicit deployment/administrative step through `flask seed-rbac`.

The catalog owns two views:

- **Permission Registry** — code-owned contracts, dependencies, current role mapping count, registry drift, shared filters/loading, and standard pagination.
- **Role Coverage** — cross-role effective permission comparison. Roles & Access intentionally keeps only role-specific permission coverage in its detail modal.

This Permission Catalog presentation is part of Access Final Lock v1.


## Activity Audit review status

Activity Audit is an Access-owned, read-only evidence workspace over the shared `notifications` operational evidence store. The hot register uses persisted `category_key`, `actor_key`, `actor_label`, and immutable `actor_snapshot_json` fields rather than reconstructing actor identity from the current User row. Notification recipient ownership remains separate through `notifications.user_id`.

The register reads hot PostgreSQL rows only. The `All Hot Records` option is intentionally explicit; verified older evidence remains under Platform Operations → Data Lifecycle after archive-and-cleanup. Notification recipient deletion cannot erase retained evidence because the Notification foreign key uses `ON DELETE SET NULL`, while actor identity remains in the immutable snapshot.
