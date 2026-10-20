# Resource Detail Modal

## Purpose

Provide one reusable, maximized detail workspace for complex Kubernetes Inventory resources without expanding or reflowing the owning table.

## Shared owner

```text
app/templates/components/resource_detail_modal.html
app/static/js/detail_rows.js
```

## Reference pages

- Node Inventory
- Namespace Inventory
- Workload Inventory
- Pod Inventory
- Service Inventory
- Ingress Inventory
- Storage Inventory
- Configuration Inventory

Inventory Overview continues to use the Side Drawer. Kubernetes Topology continues to use the Adaptive Explorer Inspector.

## Geometry

- near-fullscreen viewport usage;
- maximum desktop width: `100rem`;
- viewport-aware height with compact outer margins;
- `rounded-2xl` desktop shell;
- full available workspace on small screens;
- fixed header and footer;
- independently scrollable detail body with hidden horizontal page overflow;

## Header and summary ownership

Fetched details retain resource-specific server rendering. The modal extracts:

- `[data-resource-detail-header]` into the fixed modal header;
- `[data-resource-detail-summary]` into the fixed summary region;
- remaining evidence into the scrollable body.

Page templates must not recreate modal geometry or loading states.

## Row-action appearance

The shared `resource_detail_modal.detail_button(...)` launcher is a normal
**table-row utility action**. Its classes come directly from
`components/table_primitives.html::action_classes()`, matching the compact
neutral `View More` button in Artifact Registry Security. Icon (14px) precedes
the text label without a separate elevated/boxed icon tile. A page may pass
`class_name` for layout only, not to introduce its own geometry, colors,
shadows or interaction states.

This is an additive visual alignment: `data-resource-detail-toggle`, the
detail identity and URL attributes, accessibility semantics, focus management
and the existing JS-controlled modal/drawer host remain authoritative.
Changing the launcher must not change the loaded evidence or route permissions.


## URL contract

The active detail is represented by:

```text
?detail=<inventory-record-id>
```

Opening a detail pushes browser history. Back closes it. Forward reopens it. A directly loaded URL can fetch the detail using the page-owned endpoint template even if the row is outside the current pagination page.

## Accessibility

- `role="dialog"`;
- `aria-modal="true"`;
- labelled resource heading;
- focus trap;
- Escape close;
- focus restoration;
- explicit close buttons;
- backdrop button with accessible label.

## Prohibited patterns

- page-local modal shells;
- row expansion for dense Inventory resource details;
- replacing the entire table during detail loading;
- losing filter, pagination, Rows, or scroll state;
- body-level scrolling behind an open modal;
- raw HTML detail presentation built in JavaScript.


## Technical text wrapping

Resource names, related-resource identities, host declarations, labels, annotations, selectors, and multi-line technical values must remain visible. Do not use `truncate` in modal evidence. Shared detail rows and metadata collections use responsive key/value grids, `min-w-0`, `break-words`, and `overflow-wrap:anywhere`. Large metadata collections use the modal body scrollbar rather than nested vertical scrolling.
