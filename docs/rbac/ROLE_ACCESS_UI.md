# Roles & Access UI Contract

## 1. Design system

Roles & Access and Permission Catalog follow **KAORI Violet Infrastructure** and `docs/design/KAORI_DESIGN_SYSTEM.md`.

Required visual rules:

- use semantic Tailwind tokens from `frontend/styles.css`;
- use the shared shell, layout, content, aside, and introduction macros from `components/page_hero.html`;
- use a solid `bg-kaori-primary` authenticated hero;
- Settings and Access heroes use the shared `min-h-[15.5rem]` compact baseline and `lg:min-h-[17.5rem]` desktop baseline with an internal `lg:min-h-[14.5rem]` 8/4 grid. User Management, Roles & Access, and Activity Audit Log are the top-level references; the same shared minimum geometry applies to create/edit/detail workflows so content can grow without clipping;
- do not use gradients or raw hex colors;
- use violet for product identity and selection;
- use semantic green/amber/red/slate only for actual state;
- standard cards use `rounded-xl`; page groups and hero use `rounded-2xl`;
- final action areas align right;
- light and dark mode must both remain readable.

## 2. Roles & Access information architecture

```text
Hero
  - purpose
  - default/custom/assignment metadata
  - Permission Catalog action
  - New Custom Role action for roles.manage

Role & Access Overview
  - one shared overview container matching User Management / Identity & Access Overview
  - role population, default baseline, custom extension, and assignment-ready metrics
  - four-step Permission Registry -> Role Composition -> User Assignment -> Server Enforcement boundary

View tabs
  - Role Registry is the default tab
  - Role-Permission Matrix is a second tab on the same page
  - the matrix is generated from current database roles and backend permission sections
  - new custom roles appear automatically after the next page render
  - role columns are paginated at 5 by default with 5/10/25/50 choices so the matrix remains readable as role count grows
  - matrix role search and default/custom filtering operate on columns without changing the permission registry rows
  - the permission column and matrix header remain sticky inside a bounded scroll workspace
  - Super Admin is excluded because it is not a normal role

Role Registry tab
  - search
  - type filter
  - status filter
  - default 5 roles
  - 5/10/25/50 role choices
  - expandable role summary
  - permission preview
  - lifecycle actions

Context rail
  - role assignment flow, not a generic role-model paragraph
  - the role assignment flow uses native `<details open>` so it is visible by default and may be collapsed
  - default role coverage
  - Permission Catalog boundary
```

## 3. Role action rules

| Role type | `roles.view` | `roles.manage` |
|---|---|---|
| Default | View detail | View detail and Clone |
| Custom | View detail | View, Edit, Delete when unreferenced |

System role UI must never present Edit, Deactivate, or Delete actions.

Custom-role Delete remains disabled when user assignments or identity-provider mappings exist. The UI explanation is advisory; the server repeats the blocker checks.

## 4. Role form modes

The shared form template has four explicit modes:

- Create Custom Role;
- Clone Default Role;
- Edit Custom Role;
- Read-only Role Detail.

Mode must be clear in the hero, supporting notice, field state, permission matrix, and footer action.

## 5. Permission matrix

- group by permission module;
- show action label, stable permission key, and description;
- place Role Configuration, Permission Matrix, and the final action card in one independent primary-column stack so the matrix starts immediately below Role Configuration and never waits for the taller right-side context rail;
- align the Permission Matrix to the same primary content column width as Role Configuration instead of spanning beneath the right-side context rail;
- render the Permission Matrix as a solid, always-visible KAORI Violet card; do not wrap the outer matrix in a disclosure;
- keep each permission module collapsed by default so the solid matrix remains compact;
- provide Expand all / Collapse all in every mode, including read-only Custom Role Detail;
- allow module select/clear only in editable modes;
- provide a global Select all / Clear all control for large registries in editable modes;
- update the global control label and `aria-pressed` state from the effective checkbox selection;
- show selected permission and module counts;
- keep system/default detail fully read-only;
- explain automatic view-permission prerequisites;
- preserve selection when validation fails;
- scope all checkbox, search, count, and module operations to the current role editor root;
- keep checkbox submission functional without Alpine.js or another CDN dependency;
- keep each native checkbox positioned inside its own `relative` permission card; do not use a document-level `sr-only` checkbox that can move the whole application viewport when Firefox focuses it;
- restore document scroll origin defensively after permission focus/change while preserving the internal `<main>` scroll container;
- use `app/static/js/role_permission_editor.js` for progressive enhancement only;
- never clear and recreate every role-permission link for a small change; update relationship rows differentially;
- roll back failed role updates and render a visible operational toast instead of returning an unhandled blank response;
- keep Role Configuration, Role Summary, and Access Guardrails self-sized with `items-start`; the left configuration card must not inherit the right rail height;
- present Role Configuration as three proportional groups: role identity, operational purpose, and assignment availability;
- present Role Summary as one primary effective-coverage panel plus compact lifecycle and assignment facts instead of a flat grid of equally weighted counters;
- align the final create/update action card to the same primary content column used by Role Configuration and Permission Matrix;
- present Access Guardrails as an always-visible compact evidence card in the sticky role-impact rail;
- explain responsibility-based role design, dependency normalization, assignment impact, and the separate Super Admin boundary.

## 6. Permission Catalog

Permission Catalog is the read-only projection of the code-owned authorization registry. HTTP GET requests must never run `seed_default_rbac()` or otherwise converge the database. `flask seed-rbac` remains an explicit deployment/administrative command.

The ownership chain is:

```text
Permission Catalog
  -> defines atomic capabilities and cross-role coverage
Roles & Access
  -> bundles selected capabilities into reusable roles
User Management
  -> assigns one active role to each user account
Authorization runtime
  -> enforces the effective permission set on the server
```

Permission Catalog owns two framed workspaces:

- **Permission Registry** — code-owned contracts, module/action metadata, dependency links, role mapping count, and registry drift.
- **Role Coverage** — effective permission inclusion across default and custom roles.

The Permission Registry uses the global KAORI table contract:

- server-owned HTMX search/module/coverage filters;
- shared loading bar;
- one permission per table row;
- default `5` rows with `5`, `10`, `25`, and `50` choices;
- `Previous`, numeric pages, and `Next`;
- modal `View Details` for dependency, role-coverage, and code-to-registry evidence.

Registry drift is evidence, not an implicit mutation:

- **Canonical** — code and persisted metadata match;
- **Missing From Registry** — code contract has no persisted row;
- **Metadata Drift** — persisted metadata differs from the code contract;
- **Database Only** — a persisted key is no longer part of the current code baseline.

Database-only permissions must not be silently deleted from a read page. Review role mappings before controlled cleanup. Unused canonical permission contracts are neutral evidence and do not automatically represent a security failure.

Role Coverage is a full-width horizontally scrollable matrix owned only by Permission Catalog. Roles & Access shows role-specific permission coverage in its role-detail modal and does not duplicate the cross-role matrix.

Permission Catalog must not offer rename, delete, inline edit, direct role mutation, or an HTTP `Sync` button.

## 7. Copy standards

Use consistent terms:

- **Default role** for code-owned protected roles;
- **Custom role** for administrator-created roles;
- **Permission Catalog** for the code-owned registry;
- **Role assignment** for mapping a user to one role;
- **Super Admin** for the separate emergency authority flag;
- **Active/Inactive** for custom-role assignment availability and permission effectiveness.

Avoid calling default roles “editable templates.” They are baselines that can be cloned.


## 8. Access denied state

The authenticated HTTP 403 page follows KAORI Violet and distinguishes two conditions without exposing the requested permission key:

- **Access role unavailable** when the account has no normalized active role or the assigned role is inactive;
- **Access denied** when an active role exists but does not include the requested capability.

The page shows the current authorization state, a return-to-Welcome action, Account & Authentication access, administrator resolution guidance, and the server-side security boundary.

## 9. RBAC operational feedback and audit

Role lifecycle actions must not use Flask flash messages. Create, clone, update, failed update, blocked delete, and successful delete use the persistent KAORI operational toast and create a Notification-backed Activity Audit record with `module=rbac` metadata.

The legacy `AuditEvent` record remains for successful administrative mutations. Notification persistence is intentionally isolated from the primary mutation transaction so a notification-storage failure does not undo a successfully committed role change.

## Permission authorization flow disclosure

The **How RBAC is applied** panel uses a native `<details open>` disclosure. It is expanded by default so the permission → role → user → server-enforcement flow is immediately visible, while administrators may collapse it to prioritize registry space.
