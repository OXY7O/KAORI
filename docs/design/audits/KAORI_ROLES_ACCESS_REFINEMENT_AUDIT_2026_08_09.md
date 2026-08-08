# KAORI Roles & Access Refinement Audit — 2026-08-09

Status: UI refinement complete; Access Final Lock remains open.

## Scope

This refinement keeps `app/access/roles/` as the HTTP and presentation owner while `app/rbac/` remains the authorization-policy and code-owned permission authority.

## Decisions implemented

- Roles & Access is now a single full-width operational workspace.
- The duplicate cross-role Mapping Matrix is removed from Roles & Access. Role-specific permission coverage stays available in the role detail modal, while Permission Catalog remains the authoritative home for cross-role permission comparison and coverage.
- The index uses the KAORI Hero, Role Registry Overview, compact Role Assignment Flow, and a shared-table Role Registry.
- Role filters are server/HTMX owned and use the shared loading bar and 5/10/25/50 pagination contract. The loading bar sits in a full-width block header so it remains visible during filter and pagination requests.
- Role detail opens in the shared KAORI resource-detail modal and exposes role identity, assignment impact, role-specific permission coverage, administrative ownership, and deletion eligibility.
- The role key is grouped inline with the role name/type/state header metadata so technical identity does not render as a detached label.
- Custom-role deletion uses the shared destructive-confirmation modal and is still revalidated server-side.
- Role edit/delete mutations acquire a database row lock and carry a version token to prevent silent stale-form overwrite or stale deletion.
- Permission dependencies remain normalized by the RBAC service; the form now marks permissions that are required by the current effective scope.
- Add/Edit/Clone/Detail retain the standard sticky right rail (`xl:sticky xl:top-5`). Role Impact now uses compact operational evidence and Access Guardrails remain always visible instead of expandable.
- Authorization-effect copy is intentionally compact: `Changes apply on the next authorization check.`

## Security / correctness boundary

System roles remain code-owned and cannot be edited or deleted. Custom-role deletion remains blocked while users or Identity Provider defaults reference the role. The server rechecks those blockers while holding the role mutation lock.

Super Admin remains separate from normal roles and permissions.

## Deliberately not changed

`seed_default_rbac()` still performs convergent seeding when selected Access surfaces are opened. This is a cross-RBAC/Permission Catalog bootstrap concern and should be decided during Permission Catalog review rather than changed only from Roles & Access.

Roles & Access is not final-locked yet; Permission Catalog, Activity Audit, Directory Provisioning, and the remaining Access-wide security decisions must be reviewed first.
