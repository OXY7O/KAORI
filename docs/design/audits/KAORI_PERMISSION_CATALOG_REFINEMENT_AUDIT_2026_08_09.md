# KAORI Permission Catalog Refinement Audit — 2026-08-09

## Scope

This refinement resolves the Permission Catalog ownership decisions deferred from Roles & Access review.

## Final refinement decisions

1. Permission Catalog is strictly read-only during HTTP requests.
2. `seed_default_rbac()` is removed from Access/User request paths and remains command/bootstrap owned.
3. Registry drift is explicit evidence, not silently repaired by page load.
4. Canonical permission metadata follows current KAORI information architecture without renaming permission keys.
5. Permission Registry uses server-owned HTMX filters, shared loading, shared table grammar, and 5/10/25/50 pagination.
6. Cross-role permission comparison is owned by Permission Catalog through Role Coverage.
7. Roles & Access keeps role-specific permission coverage only.
8. Permission detail uses the shared KAORI resource-detail modal and exposes dependency/coverage/registry evidence.
9. Full-width catalog composition replaces the old documentation-heavy sticky right rail.
10. Unused code-owned permission contracts are neutral evidence, not automatically a warning.

## Drift states

- `Canonical`: code and database metadata align.
- `Missing From Registry`: code contract has no persisted permission row.
- `Metadata Drift`: persisted module/action/description differs from the code contract.
- `Database Only`: persisted permission key is no longer part of the current code baseline.

Database-only records are never silently removed from a read page. Existing role mappings must be reviewed before controlled cleanup.

## Module ownership metadata

Permission keys stay stable. Only display/grouping metadata is updated for the current IA:

- Jobs and Data Lifecycle permissions → Platform Operations.
- Secret Reveal administration → Platform Operations.
- Integration administration → Integrations.

## Roles & Access visual alignment

Role Registry Overview keeps its existing information architecture but now uses the same KAORI registry overview visual grammar as Account & Identity Posture and Permission Registry Overview: rounded-2xl shell, compact header, 11rem posture cells, 3xl primary values, semantic icon surfaces, and boundary cards on the neutral hover surface.

## Remaining open Access work

Permission Catalog is not Final Locked yet. Directory Provisioning, Activity Audit, password-reset session invalidation, and the broader Access final-lock review remain open.

## v1.21 layout refinement

- Permission Registry and Role Coverage filter bars now use the full workspace width instead of the generic flex filter primitive, with desktop-aligned columns matching other KAORI registers.
- Permission Details uses an opt-in content-driven shared resource-detail modal at `max-w-5xl`; other shared modal consumers retain the existing viewport-height default.
