# Kubernetes Inventory Resource Modal Audit — July 2026

## Scope

Node, Namespace, Workload, Pod, Service, Ingress, Storage, and Configuration Inventory.

## Decision

Dense row expansion was replaced by **Detail Style 2 — Full Workspace Modal**.

## Reasons

- complex details exceeded comfortable table-row width;
- expanded rows caused large page reflow and long table height;
- modal workspace permits wider evidence grids and full-width tables;
- current filters, page, Rows, and scroll position remain stable;
- URL-backed state supports Back, Forward, refresh, and shareable detail links;
- one shared owner replaces eight page-local interaction shells.

## Preserved patterns

- Inventory Overview retains the cluster Side Drawer;
- Kubernetes Topology retains the Adaptive Explorer Inspector;
- Detail Style 1 remains available for short row-owned evidence.

## Contract

See:

- `docs/design/components/RESOURCE_DETAIL_MODAL.md`
- `docs/design/components/DETAIL_STYLES.md`
