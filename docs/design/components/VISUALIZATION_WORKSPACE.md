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
Adaptive Explorer Grid
├── Display Controls
├── Graph or Accessible Resource List
└── Inspector
```

## Adaptive Behavior

At `2xl` and wider, the workspace may use three persistent panes:

```text
18rem Controls | Flexible Canvas | 22rem Inspector
```

Below `2xl`:

- the visualization receives the primary width;
- Controls opens as a left drawer;
- Details opens as a right drawer;
- one shared backdrop closes either drawer;
- Escape closes open drawers;
- the current graph, filters, selection, and local view state remain unchanged.

The fixed 20rem `context_rail` is not used for visualization controls or inspectors. Those panes are interactive parts of the visualization, not supporting page context.

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

## DRY Rules

Page templates provide filters, controls, panels, and domain content. The shared component owns shell geometry, header hierarchy, adaptive pane classes, canvas height, loading placement, and the `adaptive-explorer` audit marker.

Do not copy its shell or three-pane grid classes into another page.
