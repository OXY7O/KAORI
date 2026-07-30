# Kubernetes Topology Pattern

## Canonical Composition

```text
Canonical Hero
Compact Inventory Data Snapshot
Visualization Workspace Style 1 — Adaptive Explorer
├── Filter Bar
├── Local Status / Warning Region
├── Canvas Toolbar
│   ├── Tab Style 2: Graph / Resource List
│   ├── Controls
│   ├── Details
│   ├── Fit
│   ├── Reset
│   └── Export
├── Display Controls
├── Graph or Accessible Resource List
└── Topology Inspector
    └── Tab Style 2: Details / Relationships
```

## Information Ownership

- Hero owns topology posture: Clusters, Namespaces, Resources, Relationships, and Graph Coverage.
- Inventory Data Snapshot owns exact collection time, source, scope, committed coverage, and exceptions.
- Filter Bar owns graph data scope.
- Canvas Toolbar owns local presentation and export actions.
- Inspector owns selected resource or relationship context.

The hero must not repeat exact sync time or snapshot source.

## Data Boundary

Topology reads current committed inventory rows. Filter, refresh, list, inspector, layout, and export interactions do not query the Kubernetes API live.

Graph payloads are cached by committed generation and filter combination. Query paths load only resource families required by scope/depth, and service-to-pod matching is indexed by cluster and namespace.

## Accessibility

- Graph uses `role="img"` with a concise description, not `role="application"`.
- Resource List exposes the same visible resource scope as a canonical table.
- Search follows combobox/listbox/option semantics and supports Arrow Up, Arrow Down, Enter, and Escape.
- The list and inspector remain available if Cytoscape cannot load.
- View state uses `?view=list` when Resource List is active.

## Loading and Errors

The visualization workspace owns one local loading bar for filter and Refresh Graph requests. Display-only changes do not show loading.

A truncated graph uses a warning callout with omitted counts. Renderer errors preserve Resource List access.
