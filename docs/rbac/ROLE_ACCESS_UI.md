# Roles & Access UI Contract

## 1. Design system

Roles & Access and Permission Catalog follow **KAORI Violet Infrastructure** and `docs/design/KAORI_DESIGN_SYSTEM.md`.

Required visual rules:

- use semantic Tailwind tokens from `frontend/styles.css`;
- use the shared shell, layout, content, aside, and introduction macros from `components/page_hero.html`;
- use a solid `bg-kaori-primary` authenticated hero;
- Settings and Access heroes use the same `min-h-[15rem]` shell, `min-h-[12rem]` grid, 8/4 desktop layout, title scale, padding, and 12rem minimum context panel;
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

Summary metrics
  - total roles
  - default roles
  - custom roles
  - active roles

Role registry
  - search
  - type filter
  - status filter
  - default 5 rows
  - 5/10/25/50 row choices
  - expandable role summary
  - permission preview
  - lifecycle actions

Context rail
  - role model explanation in a violet distinction block
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
- show selected permission and module counts;
- keep system/default detail fully read-only;
- explain automatic view-permission prerequisites;
- preserve selection when validation fails.

## 6. Permission Catalog

Permission Catalog is read-only and should answer:

- what capability a key grants;
- which module/action it belongs to;
- which roles currently use it;
- whether it is unassigned;
- that permission creation is a code change.

It must not offer rename, delete, inline edit, or direct role mutation controls.

The registry uses the global KAORI pagination contract because permission volume is expected to grow:

- default `5` permission cards per page;
- selectable `5`, `10`, `25`, and `50`;
- search and module filters reset to page 1;
- pagination operates on effective filtered permissions while retaining module grouping;
- empty filtered results show an explicit no-match state;
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
