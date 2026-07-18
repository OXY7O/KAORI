# Roles & Access UI Contract

## 1. Design system

Roles & Access and Permission Catalog follow **KAORI Violet Infrastructure** and `docs/design/KAORI_DESIGN_SYSTEM.md`.

Required visual rules:

- use semantic Tailwind tokens from `frontend/styles.css`;
- use the shared shell, layout, content, aside, and introduction macros from `components/page_hero.html`;
- use a solid `bg-kaori-primary` authenticated hero;
- Settings and Access heroes use the shared `min-h-[15.5rem]` and `xl:h-[15.5rem]` shell, 8/4 desktop layout, title scale, and padding. User Management is the top-level reference and Add User is the create/edit/detail reference;
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
  - new custom roles appear as matrix columns after the next page render
  - Super Admin is excluded because it is not a normal role

Role Registry tab
  - search
  - type filter
  - status filter
  - default 5 rows
  - 5/10/25/50 row choices
  - expandable role summary
  - permission preview
  - lifecycle actions

Context rail
  - role assignment flow, not a generic role-model paragraph
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
- allow module select/clear only in editable modes;
- provide a global Select all / Clear all control for large registries;
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
- present Access Guardrails as a native expandable section with `open` set by default;
- explain responsibility-based role design, dependency normalization, assignment impact, and the separate Super Admin boundary.

## 6. Permission Catalog

Permission Catalog is the read-only UI projection of the backend-owned permission registry. Permission definitions originate in `app/rbac/defaults.py` and are synchronized to the database through `flask seed-rbac`.

The ownership chain is:

```text
Permission Catalog
  -> defines atomic capabilities
Roles & Access
  -> bundles selected capabilities into reusable roles
User Management
  -> assigns one active role to each user account
Authorization runtime
  -> enforces the effective permission set on the server
```

Permission Catalog should answer:

- what capability a key grants;
- which module/action it belongs to;
- which roles currently use it;
- whether it is unassigned;
- that permission creation is a code change.

It must not offer rename, delete, inline edit, or direct role mutation controls. Roles & Access owns permission-to-role composition; User Management owns role-to-user assignment. Identity Provider configuration may choose a default role for JIT-provisioned users, but it does not create permission keys or grant Super Admin.

The registry uses the global KAORI pagination contract because permission volume is expected to grow. Its pagination unit is the top-level permission section/module, not individual permission cards:

- default `5` module sections per page;
- selectable `5`, `10`, `25`, and `50` sections;
- every visible module keeps all matching permission cards together on the same page;
- a module is never split across two pages;
- search and module filters reset to page 1;
- search may reduce the permission cards shown inside a module, while pagination continues to count the matching modules;
- empty filtered results show an explicit no-match state;
- the footer reads `Showing 1–5 of 12 sections`, followed by the numeric page-size selector;
- the registry/content column uses top alignment so a taller context rail cannot create blank space below its footer;
- the authorization boundary explanation is presented in a violet distinction block.

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
