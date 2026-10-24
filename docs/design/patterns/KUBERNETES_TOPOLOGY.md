# Kubernetes Topology Pattern

## Canonical Composition

```text
Canonical Hero
Compact Inventory Data Snapshot
Visualization Workspace Style 1 — Adaptive Explorer
├── Header Actions: Reload Snapshot + conditional Clear Filters (canonical compact peer actions)
├── Filter Bar
├── Local Status / Warning Region
├── Canvas Toolbar
│   ├── Tab Style 3: Graph / Resource List (compact toolbar mode)
│   ├── Controls → left drawer
│   ├── Details  → right drawer
│   ├── Fit
│   ├── Reset
│   └── Export
├── Full-Width Graph or Accessible Resource List
├── Display Controls → hidden until requested
└── Topology Inspector → hidden until requested/selection
    └── Tab Style 3: Details / Relationships (full-width equal-segment inspector mode)

Compact segmented tabs must render the configured `data-*` attribute with the tab key as its value. Topology JavaScript reads those values through `dataset` for Graph/List and Details/Relationships activation; a valueless data attribute is not a valid interaction contract.
```

## Information Ownership

- Hero owns topology posture: Clusters, Namespaces, Resources, Relationships, and Graph Coverage.
- Inventory Data Snapshot owns exact collection time, source, scope, committed coverage, and exceptions.
- Header actions own explicit committed-snapshot reload and the canonical conditional Clear Filters action. Both are peer utilities and use the same compact header-action geometry; Reload Snapshot is not styled as a dominant primary CTA.
- Filter Bar owns graph data scope.
- Canvas Toolbar owns local presentation and export actions.
- Inspector owns selected resource or relationship context. The existing Details inspector shows a compact **Relationship Summary**, grouped by visible committed edge type and direction; a keyboard-accessible **View Relationships** action opens the existing full Relationships tab without duplicating the graph or making live provider requests.

The hero must not repeat exact sync time or snapshot source.

## Data Boundary

Topology reads current committed inventory rows. Filter, reload, list, inspector, layout, and export interactions do not query the Kubernetes API live.

Graph payloads are cached by committed generation and filter combination. Query paths load only resource families required by scope/depth, and service-to-pod matching is indexed by cluster and namespace.

## Accessibility

- Graph uses `role="img"` with a concise description, not `role="application"`.
- Resource List exposes the same visible resource scope as a canonical table.
- Search follows combobox/listbox/option semantics and supports Arrow Up, Arrow Down, Enter, and Escape.
- The list and inspector remain available if Cytoscape cannot load.
- View state uses `?view=list` when Resource List is active.

## Loading and Errors

The visualization workspace owns one local loading bar for filter and **Reload Snapshot** requests. Filter changes already fetch the matching committed topology payload automatically; Reload Snapshot is the explicit same-scope re-fetch used to pick up a newer committed inventory generation without changing filters. It is a JavaScript data fetch, not an HTMX page refresh. **Clear Filters** reuses the canonical shared action, resets Cluster/Namespace/Resource Scope/Depth/Search to defaults, preserves layout/view display state, and reloads the default committed graph. Display-only changes do not show loading.

A truncated graph uses a warning callout with omitted counts. Renderer errors preserve Resource List access.

## Readable Graph Node Refinement

The canonical graph uses compact rounded domain badges with a resource-type glyph and semantic status dot. The object name is rendered below the badge as one external line with bounded ellipsis, while the complete name and type remain available in Resource List and Details. Containment lines are quiet dashed orthogonal connectors without arrowheads; dependency labels remain progressive-disclosure content.

## Relationship Focus and Namespace Grouping

Selecting a graph resource uses the existing one-hop neighborhood focus to foreground its related resources and their operational edges, while quiet containment links stay subordinate. The Details inspector presents bounded, direction-aware counts from the **visible committed edges** and delegates full navigation to the existing Relationships tab. Namespace boundary overlays appear only when their scope has visible non-Namespace resources; their labels report the visible resource count, without implying unseen or live Kubernetes resources.

## Compact Hierarchy and Viewport Safety

Hierarchy View retains the existing Cytoscape breadth-first layout, with compact node-count-aware spacing (small graphs through 8 resources; moderately dense through 35; larger views). Dependency View retains its existing COSE layout geometry. Both layouts disable Cytoscape's layout-level automatic fitting; KAORI owns final viewport selection after layout settles.

- **Compact scope:** Fit the visible graph and external resource labels in the canvas with bounded safety margins.
- **Dense scope:** When more than 12 visible resources would require a full-graph zoom below 0.72, initially zoom to 0.82 around the selected node, active Namespace, or Cluster anchor. This is a **focal viewport**, not evidence truncation: all committed nodes and relationships remain in the graph, Resource List, inspector, and exports. Display a neutral accessible hint naming the resource count and explaining pan/zoom plus Fit. Keep Resource List as the accessible complete-identity view.
- **Fit:** The explicit toolbar button still fits the **entire** visible graph, including external labels and a bounded margin. If this overview requires microscopic labels, an accessible hint distinguishes overview from readable focus and directs the operator to zoom or Resource List. Do not claim every label is readable simultaneously in a dense overview.
- **Resize and view switches:** A focused graph does not automatically refit because its offscreen nodes are deliberately outside the focal viewport; retain operator pan/zoom. Fit again only when the unfocused visible graph is clipped by an actual viewport resize, and initialize a viewport when switching from an initially hidden Resource List.
- **Reset/layout/filter/reload:** Apply the readable focal decision to a newly laid-out graph, without changing filters, committed graph evidence, relationship counts, or export content.

The graph's existing pan/zoom and hierarchy collapse interactions remain available. Namespace grouping, list fallback, current committed generation read boundary, truncation warning, and dark-mode surface tokens do not change.

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

## Canvas-First Drawer Contract

Topology is a canvas-first workspace. Controls and Topology Details remain overlay drawers at every breakpoint; they never become persistent desktop columns. The canvas therefore keeps the full workspace width until the operator intentionally opens a drawer. Selecting a resource or relationship opens the right Details drawer, while Display Controls opens from the toolbar on demand. Closing either drawer restores the unchanged full-width graph.

The right drawer uses the shared visualization drawer geometry (`max-w-2xl`) and does not participate in page grid sizing. The wider inspector is reserved for technical metadata and relationship review; the left Controls drawer remains compact. `API Server` keeps the canonical horizontal field row. Its value is single-line, right aligned, and truncated only when the endpoint exceeds the available drawer width. The complete endpoint remains exposed through the native `title` attribute. A dedicated stacked-row compatibility template is prohibited.


## Bounded Shallow Graph Source (2026-10-11)

At Depth 1, only Cluster, Namespace, and Node elements participate in graph
projection. Namespace and Node ORM fetches therefore use a deterministic
`max_nodes` SQL window, with independent exact committed-generation SQL counts
for omitted-type reporting. Namespace selector bootstrap projects DISTINCT scalar
cluster/namespace values rather than full Namespace ORM records. Deeper graph
modes reuse current-generation, type-specific SQL candidate windows, a
relationship-safe parent budget, and scalar selector/reference qualification
before ORM projection. Do not apply an unconditional SQL LIMIT to a
relationship-sensitive source without preserving graph/omission equivalence.


## Bounded relationship candidates (Depth 2 / 3 / Full)

Graph parent rows (Cluster + current Namespace) always consume the visible
350-node budget before resources. For deep scopes, Namespaces are SQL-counted
and only the available parent-prefix is materialized. If parents fill the
budget, resource families receive a zero-row ORM budget but still report
exact eligible committed-generation SQL totals, preserving omitted-by-type
evidence. If parents fit, families use stable type-specific SQL prefixes and
independent exact counts, including ConfigMap/Secret and PVC/PV quotas.
Namespace-backed nodes require a current committed Namespace parent.
Namespace-specific Node placement uses correlated committed SQL EXISTS.

All/Compute Pods use bounded type prefixes. Configuration and Storage Pods
are first filtered in SQL using the presence of committed JSON references;
they then use the same deterministic bounded ORM/count path. Deep Networking
Pod relevance requires **all** current Service selectors, including selectors
from Services beyond the visible prefix. The repository streams selector
scalar rows in batches, retains distinct nonempty selectors by
cluster/namespace, scans only committed Pod ID/labels scalars to count the
matching cohort, and materializes at most the graph-budget matching Pod
records. Rendered Service ORM rows themselves use bounded SQL prefixes.
The selector index scales with the number of distinct selector maps and its
high-cardinality performance must still be measured; it is not a bounded
selector-index memory guarantee or proof of a latency target.

Namespace-scoped PVC/PV queries retain the earlier current-generation
correlated SQL EXISTS on the PVC's referenced volume name (same cluster and
selected namespace). Claims and matching volumes are SQL-counted and
independently limited. Preserve deterministic visible nodes/edges, complete
Service selector semantics, precise omission counts, cache authority and the
committed-state read boundary. No provider API calls, new graph components or
unconditional LIMIT across relationship-sensitive sets.

## Reusable topology presentation primitives

**Authority:** Kubernetes Inventory Topology remains the canonical visual and
interaction reference. New topology domains MUST consume existing KAORI
primitives rather than copying independent markup.

- `app/templates/components/visualization_workspace.html` — the shared
  canvas-first workspace, bounded loading bar, and overlay drawer geometry
- `app/templates/components/segmented_tabs.html` — Compact Segmented Tabs for
  Graph/Resource List and Details/Relationships
- `app/templates/components/topology_primitives.html` — shared toolbar action
  and export classes, **Resource List row**, **inspector field row**,
  **relationship card**, **relationship summary chip**, and
  **empty relationships** templates

Kubernetes Inventory and Artifact Registry Runtime both import these
primitives. Their IDs remain domain-prefixed but geometry, typography, icons,
interactive affordances, and semantic badge slots must remain identical.

For Cytoscape external labels, the Kubernetes topology style is the source
of truth: font-weight **400**, min zoomed font **8**, external label max width
**220px** (240px for Cluster), 11px vertical margin, 0.94-opacity surface
background, tokenized border and ellipsis rendered by Cytoscape. Do not
truncate the identity artificially at a fixed character count or raise node
label weight in a consuming domain.

The status badge is a **presentation slot**, not a shared health conclusion.
Kubernetes binds committed resource operational status; Registry binds
artifact scan exposure for Artifact nodes and correlation readiness for
other nodes. A ready correlation is evidence readiness, not "Healthy".
Any omitted graph records and uncertain evidence remain explicit.

The topology-specific graph/data builders, event handlers and relationship
semantics remain domain-owned; do not extend the shared primitives with
provider-specific correlation logic.

