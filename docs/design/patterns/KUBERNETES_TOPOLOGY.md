# Kubernetes Topology Pattern

## Canonical Composition

```text
Canonical Hero
Compact Inventory Data Snapshot
Visualization Workspace Style 1 — Adaptive Explorer
├── Filter Bar
├── Local Status / Warning Region
├── Canvas Toolbar
│   ├── Tab Style 3: Graph / Resource List
│   ├── Controls
│   ├── Details
│   ├── Fit
│   ├── Reset
│   └── Export
├── Display Controls
├── Graph or Accessible Resource List
└── Topology Inspector
    └── Tab Style 3: Details / Relationships
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

## Readable Graph Node Refinement

The canonical graph uses compact rounded domain badges with a resource-type glyph and semantic status dot. The object name is rendered below the badge as one external line with bounded ellipsis, while the complete name and type remain available in Resource List and Details. Containment lines are quiet dashed orthogonal connectors without arrowheads; dependency labels remain progressive-disclosure content.

## Canonical Server Architecture

Topology does not use one monolithic service or an internal compatibility wrapper. Ownership is split by responsibility:

- `service.py` owns filter normalization, cache orchestration, and the public page/graph entry points;
- `repository.py` owns committed-generation queries and resource-family query bounds;
- `node_builder.py` owns resource node projection;
- `edge_builder.py` owns supported relationship projection;
- `graph_builder.py` owns final graph assembly and summary;
- `presentation.py` owns node/edge payload formatting and graph limits;
- `contracts.py` owns typed graph inputs and state.

The browser loads `topology.js` directly. That module imports the Cytoscape renderer itself; no bootstrap file, global renderer alias, or secondary workspace loader is permitted.

## Domain Icon Surface Contract

Every Topology domain icon uses the complete three-token surface in both themes:

- `*-fill` is the icon-shell background;
- `*-border` is the visible shell outline;
- `*-text` is the glyph foreground.

A domain class must never assign the translucent `*-fill` token to `color`. Resource Visibility,
Resource List rows, search results, graph details, and the selected-resource inspector all reuse the
same `.kaori-topology-domain-*` classes so light and dark mode cannot diverge.

## Inspector Width and API Server Presentation

The Adaptive Explorer uses a `26rem` right inspector at the `2xl` breakpoint and `max-w-md` for the
mobile right drawer. This gives operational identities enough width without reducing the graph to a
secondary column.

`API Server` uses the canonical horizontal field row. Its value is single-line, right aligned, and
truncated only when the endpoint exceeds the available width. The complete endpoint remains exposed
through the native `title` attribute. A dedicated stacked-row compatibility template is prohibited.
