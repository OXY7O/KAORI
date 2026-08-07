# Visualization Workspace

## Purpose

`components/visualization_workspace.html` owns the outer shell and adaptive layout for dense interactive visualizations that cannot be represented as an ordinary table, form, dashboard card, or fixed side rail.

The first approved variant is **Visualization Workspace Style 1 — Adaptive Explorer** with semantic key `adaptive-explorer`.

## Reference Implementation

Kubernetes Topology is the canonical reference.

## Composition

```text
Workspace Header
Filter Bar
Local Status / Warning Region
Canvas Toolbar
Canvas-First Explorer
├── Graph or Accessible Resource List
├── Display Controls → on-demand left drawer
└── Inspector       → on-demand right drawer
```

## Canvas-First Behavior

The visualization is the primary working surface at **every viewport width**. Display Controls and Details must never become persistent columns that permanently reduce the graph width.

Canonical behavior:

- the graph/list canvas receives the full available workspace width;
- Controls opens as a left overlay drawer;
- Details opens as a right overlay drawer;
- selecting a graph resource or relationship opens Details on demand;
- opening one drawer closes the other;
- one shared backdrop closes the active drawer;
- Escape closes open drawers;
- closing a drawer restores the exact full-width canvas without changing graph state;
- drawer open/close must not refetch inventory or reset filters, layout, selection, or current view.

This rule applies on large desktop screens as well as laptop/mobile widths. A three-column persistent explorer is not part of the canonical KAORI Topology contract.

The fixed `context_rail` is not used for visualization controls or inspectors. Those surfaces are progressive-disclosure tools owned by the visualization itself.

## Header Contract

The header owns:

- one visualization title;
- one sentence-case description;
- one icon surface;
- at most one section-level action;
- one section-owned loading bar.

Fit, Reset, view switching, display controls, and exports belong in the canvas toolbar, not the header.

## Canvas Contract

- Height uses the shared `.kaori-visualization-canvas` tokenized class.
- The graph panel exposes a concise accessible description.
- Do not use `role="application"` unless complete keyboard graph navigation exists.
- A textual Resource List is required when graph content cannot be navigated equivalently with a keyboard and screen reader.
- Renderer failure must not remove access to the committed payload; switch to Resource List and show a concise error.
- `Fit` operates against the full canvas dimensions after a drawer closes.

## Drawer Contract

- Controls and Details are hidden by default.
- Drawer geometry is owned by `drawer_pane_classes()`.
- Page templates must not add breakpoint utilities that convert either drawer into a persistent pane.
- Close controls remain visible at every breakpoint.
- Details may be opened by the toolbar or automatically after selecting a resource/relationship.
- The backdrop uses KAORI surface tokens and must remain light/dark safe.

## DRY Rules

Page templates provide filters, controls, panels, and domain content. The shared component owns shell geometry, header hierarchy, drawer geometry, canvas height, loading placement, and the `adaptive-explorer` audit marker.

Do not copy its shell or drawer geometry into another page. Do not add a local desktop-only persistent grid for Topology.
