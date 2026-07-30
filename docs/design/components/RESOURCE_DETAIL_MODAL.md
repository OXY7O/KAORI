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
- maximum desktop width: `90rem`;
- viewport-aware height with compact outer margins;
- `rounded-2xl` desktop shell;
- full available workspace on small screens;
- fixed header and footer;
- independently scrollable detail body.

## Header and summary ownership

Fetched details retain resource-specific server rendering. The modal extracts:

- `[data-resource-detail-header]` into the fixed modal header;
- `[data-resource-detail-summary]` into the fixed summary region;
- remaining evidence into the scrollable body.

Page templates must not recreate modal geometry or loading states.

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
