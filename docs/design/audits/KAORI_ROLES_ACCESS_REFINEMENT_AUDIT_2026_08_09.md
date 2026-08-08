# KAORI Roles & Access Refinement Audit — 2026-08-09

Status: UI refinement complete; Access Final Lock remains open.

## Scope

This refinement keeps `app/access/roles/` as the HTTP and presentation owner while `app/rbac/` remains the authorization-policy and code-owned permission authority.

## Decisions implemented

- Roles & Access is now a single full-width operational workspace.
- The duplicate cross-role Mapping Matrix is removed from Roles & Access; Permission Catalog remains the authoritative permission-registry workspace.
- The index uses the KAORI Hero, Role Registry Overview, compact Role Assignment Flow, and a shared-table Role Registry.
- Role filters are server/HTMX owned and use the shared loading bar and 5/10/25/50 pagination contract.
- Role detail expands below the row and exposes assignment impact, provider-default references, permission coverage, protected-default ownership, and deletion eligibility.
- Custom-role deletion uses the shared destructive-confirmation modal and is still revalidated server-side.
- Role edit/delete mutations acquire a database row lock and carry a version token to prevent silent stale-form overwrite or stale deletion.
- Permission dependencies remain normalized by the RBAC service; the form now marks permissions that are required by the current effective scope.
- Add/Edit/Clone/Detail retain the standard sticky right rail (`xl:sticky xl:top-5`) and now emphasize role impact instead of generic summary metrics.

## Security / correctness boundary

System roles remain code-owned and cannot be edited or deleted. Custom-role deletion remains blocked while users or Identity Provider defaults reference the role. The server rechecks those blockers while holding the role mutation lock.

Super Admin remains separate from normal roles and permissions.

## Deliberately not changed

`seed_default_rbac()` still performs convergent seeding when selected Access surfaces are opened. This is a cross-RBAC/Permission Catalog bootstrap concern and should be decided during Permission Catalog review rather than changed only from Roles & Access.

Roles & Access is not final-locked yet; Permission Catalog, Activity Audit, Directory Provisioning, and the remaining Access-wide security decisions must be reviewed first.
