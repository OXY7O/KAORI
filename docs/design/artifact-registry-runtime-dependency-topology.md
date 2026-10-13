# Artifact Registry — Runtime Dependency Topology

**Authority:** #1692 (bounded implementation), #897 (Registry ↔ Kubernetes correlation);
#558 (provider-neutral Registry foundation), #747 (page-level navigation),
`docs/design/patterns/KUBERNETES_TOPOLOGY.md` (shared visualization grammar).

## Placement and boundaries

**Artifact Registry → Runtime** is a sidebar capability. Its canonical
level-three Integrated Workspace Tabs appear **above the Hero**, using the
existing `capability_navigation` injection from `layouts/app.html` and
`components/workspace_tabs.html::render_navigation`:

1. **Overview** — `/artifact-registry/runtime/overview`; default sidebar
   destination, committed correlation posture, freshness, evidence coverage
   and links to detailed explorations.
2. **Runtime Usage** — `/artifact-registry/runtime`; existing searchable
   Runtime Bindings table/filter/detail registry, preserved for backwards
   compatibility with deep links and other domain handoffs.
3. **Topology** — `/artifact-registry/runtime/topology`; read-only
   artifact-centric Adaptive Explorer graph/list/inspector.

The Runtime menu is named **Runtime**, not `Runtime Usage`. Tab labels are
exactly **Overview**, **Runtime Usage**, **Topology**. They are page-level views,
not an additional sidebar level or an inner graph tab family. The
`/artifact-registry/runtime/topology/data` endpoint retains its existing
`artifact_registry.view` permission and read-only filters. Tab navigation
preserves supported URL scope filters while not carrying list pagination or
graph-only display state.

The topology is a read-only, artifact-centric graph over the existing
committed RegistryWorkloadBinding materialization. It is **not** an additional
provider API, relationship database, scanner, or Intelligence recommendation
lifecycle. Graph and Resource List present the **same bounded query slice**,
and the inspector links back to the canonical Runtime Bindings view.

## Relationship model

```text
Registry artifact digest
    └─ runtime_usage (derived RegistryWorkloadBinding evidence)
        Kubernetes cluster
            └─ contains → Namespace
                └─ contains → Workload
                    └─ owns → Pod (container references in inspector)
```

The parent hierarchy from Cluster to Pod is **presentation context** extracted
from the binding, not a separate assertion of complete Kubernetes resource
ownership. Workload name/type can be unresolved; this is displayed as
`Not Resolved`, never invented. Artifact identity is source-scoped and
digest-first; tag-only correlation remains lower-confidence. A single
artifact-to-cluster edge may aggregate both match types and is then
`mixed`, with individual evidence available in Resource List / inspector.
Vulnerability counts belong to the Registry Artifact and must never be summed
as independent new CVEs on every affected Pod or Cluster.

## Read model and completeness

1. Start from active/enabled Registry source identity, using the same
   normalized SQL filters as Runtime Usage (Registry source, cluster,
   namespace, artifact, match type, security exposure and search).
2. Compute exact in-scope committed binding count before display limiting.
3. Select at most **45 bindings** in stable artifact/cluster/namespace/
   workload/pod/ID order; hydrate only those matching entities.
4. Deduplicate graph nodes/edges deterministically; expose total, displayed,
   omitted, and visible-node counts to the client.
5. Scope, identity, and confidence are never broadened to satisfy missing
   evidence. An invalid selected Registry source fails closed.
6. Load Cytoscape only for the graph. The accessible Resource List and
   inspector use the same response and remain usable if Cytoscape fails.

A graph slice is **not** a complete fleet blast-radius conclusion when
`omitted_bindings > 0`. Refine scope rather than treating omitted edges as
absent consumers.

## Readiness and negative evidence

The graph exposes the existing Runtime Correlation readiness:
`not_materialized`, `inputs_changed`, `refreshing`,
`refresh_failed`, `stale`, `ready`. A previous committed correlation
may be displayed while provisional, but never labeled as current/complete.
No bindings under incomplete evidence is **not** a verified "No Impact".

The normal UI neither calls Harbor nor queries live Kubernetes, and Reload
Snapshot re-fetches only the committed KAORI graph JSON. Synchronization
and materialization remain owned by canonical jobs.

## UI and interaction

Reuse `visualization_workspace.html` (Adaptive Explorer), Violet semantic
tokens, shared Hero, Inventory Data Snapshot, table helpers, overlay inspector,
graph/list fallback, and responsive/light/dark patterns. Do not add a third
sidebar level. Filter changes are URL-backed and bounded; local graph
presentation actions do not change the committed data. The list defaults to
five rows per page. Export PNG is an image of the **visible** graph slice,
not an authoritative fleet report.

## Shared Kubernetes Topology visual grammar (#1692 visual review)

The Runtime Topology shell follows `docs/design/patterns/KUBERNETES_TOPOLOGY.md`
and `docs/design/components/TOPOLOGY_PALETTE.md`, **not** a second graph
design system. Reuse the existing `visualization_workspace.html` Adaptive
Explorer (including `adaptive_grid_classes`, `drawer_pane_classes`, and
`canvas_classes`), shared `segmented_tabs.html` Tab Style 3,
`table.html`, `table_label.html`, and the shared empty-state partial.

- Toolbar: Graph / Resource List, Controls, Details, Fit, Reset, Export
  (PNG / bounded JSON) in the same hierarchy as Kubernetes Topology.
- Controls and Details are overlay drawers, never persistent columns; the
  canvas keeps full width at every breakpoint. Opening one closes the other.
- The compact tokenized **domain badge** (AR / CL / NS / WL / PD with a
  semantic evidence marker) uses the K8s palette domain fill/border/text.
  External single-line names use bounded ellipsis and the full identity is
  available on hover, via keyboard-accessible Resource List and Details.
  No raw color hex or oversized label-inside-node rectangles.
- Hierarchy uses the existing Cytoscape breadth-first geometry and label
  bounding boxes. **Branched** relationships follow Kubernetes' top-down
  tree while a single Registry-to-Pod chain is rotated left-to-right to
  avoid a vertical stick. Dependency mode uses COSE. Fit uses the visible
  graph bounding box including external labels, bounded margins, and a cap
  on over-magnification.
- Dashed quiet containment, solid ownership, and digest/tag-confidence-aware
  runtime edges preserve graph semantics. Relationship labels are hidden by
  default at every graph size, and appear only on edge hover, selection,
  or explicit Always Show control, per the current Kubernetes authority.
  Hiding an edge or resource type is **display-only**.
- Node selection focuses the local neighborhood and opens the right inspector.
  The inspector follows the canonical Kubernetes **identity header → Highlight
  Path / Collapse → Details / Relationships tabs → relationship summary →
  interactive related-resource cards**. Artifact/Cluster selections also show
  a bounded mini-map that centers the main graph, not a provider-side query.
  Registry-specific committed bindings, match confidence, scan posture and
  readiness stay scoped to their authoritative sources.
- Resource List is now a **resource-node explorer**, as in Kubernetes Topology:
  Resource, Type, Cluster, Namespace, Evidence, Relationships and View Details,
  five rows per page. Node scopes are resolved from already-returned bounded
  edges, never from a new live query. The committed binding counts remain in
  Snapshot/toolbar; list node counts must not be misreported as binding totals.
- The Display Controls' Group by Namespace toggle draws optional boundaries
  for the visible committed Namespace subtree, without creating new edges or
  altering correlation results. Resource/relationship hiding, collapse, and
  graph focus remain presentation-only and must not hide omitted data counts.
- List fallback and a committed-only Reload remain available if Cytoscape
  fails. Export never implies full coverage when omitted bindings are nonzero.
- Correlation readiness `inputs_changed` and other provisional states remain
  explicit warnings. The browser never materializes new data or treats missing
  findings as remediated.

The Cytoscape event controller is domain-specific because the Registry's
`RegistryWorkloadBinding` evidence and Kubernetes Inventory topology have
different provenance/relationship semantics. It consumes the same existing
shared UI and palette contracts; a new graph abstraction is not introduced
without demonstrated multi-domain value.

### Canonical filters, loading and mini-map (2026-10-13 UAT feedback)

The Runtime Topology filter UX follows Kubernetes Inventory Topology:

- Six scoped fields (Registry Source, Cluster, Namespace, Match Type,
  Security Exposure and Artifact/Workload Search) share a single row at
  desktop `lg` width; smaller breakpoints wrap responsively.
- Filter selects automatically fetch the committed JSON graph; search is
  debounced (350 ms), and there is **no Apply Filters action**. The browser
  updates the filter URL while retaining graph-only `view` and `layout`
  state. As in Kubernetes Topology, the canvas renderer uses a bounded
  client-side JSON fetch rather than a second HTML/HTMX fragment endpoint.
  HTMX-based registry table pages remain unchanged.
- **Clear Filters** uses the existing `table_registry.clear_filters_action`
  in the Adaptive Explorer header (before Reload Snapshot), hidden when
  no filters are active. Clearing includes the focused artifact scope and
  does not require a page refresh.
- The header's existing shared `loading_bar.html` must actually activate
  during initial requests, filter changes and Reload Snapshot; follow
  Kubernetes Topology's `htmx-request` loading class and disable Reload
  until the latest request completes. Abort from an earlier request must
  never hide the latest request's progress bar.
- The inspector mini-map uses the K8s pixel-ratio-aware, tokenized Canvas2D
  miniature of the *visible selected artifact/cluster branch*. It includes
  edges, glyph-domain colors, selected-node emphasis and a dashed current
  viewport rectangle; it should be refreshed after graph layout, zoom,
  pan, position and resize, rather than preserving a stale one-dot sketch.
  If there are fewer than two visible related nodes, the mini-map is
  hidden rather than implying a dependency topology that is not supported.

These interactions are presentation-only; committed RegistryWorkloadBinding,
readiness, match confidence, permissions and the bounded projection remain
unchanged. They do not introduce a provider API or bypass CI/CD HOLD.

### Visual UAT focus

Verify the one-artifact single-chain example against Kubernetes Topology
side-by-side; inspect labels at 320px, 768px, and desktop width in both themes.
Also test multiple artifacts/branches, long labels, tag/mixed confidence,
relationship hiding, keyboard drawer closure, Graph/List parity, stale
committed correlation warnings, bounded omissions, export and renderer failure.
The K8s Topology renderer and contracts must remain unchanged.

## Current limitations and UAT gates

- #1441 remains the canonical source identity/container-precision follow-up;
  #929 remains materialization performance/heartbeat authority.
- The MVP does not infer source-control lineage, deployments, network
  communication, Service Catalog dependencies, or operational causality.
- DevContainer UAT must verify correct visible relationships, evidence
  states, filters, narrow viewport, light/dark, keyboard access, renderer
  fallback, and omission warnings with >45 in-scope bindings.
- Do not proceed to Developer Check, Full Admission, staging/main promotion
  or release without explicit human acceptance. Review integration target:
  `kaori/review/staging-uat`.

## Canonical presentation reuse — K8s reference

The Runtime Topology now consumes **the same shared Jinja primitives** as
Kubernetes Inventory Topology from
`app/templates/components/topology_primitives.html`: toolbar action styles,
Resource List row, field rows, directional relationship cards, relationship
summary chips and relationship empty state. These primitives are deliberately
generic and rely on domain-prefixed template IDs and data attributes.

The Registry JavaScript supplies only domain-specific evidence: full artifact
identity, Registry source, digest/tag confidence, scan severity, and committed
correlation readiness. The Resource List and Details status slots use the same
KAORI semantic badge geometry and iconography as Kubernetes, but must not
display healthy runtime status merely because a correlation snapshot is ready.

The canonical Graph external label uses Kubernetes typography without a
30-character JavaScript cutoff; Cytoscape manages width and ellipsis. All
related changes to the shared component must be tested against **both**
Kubernetes and Registry topology contracts before review. New topology
features should reuse these components rather than introducing another
workspace/list/inspector design family.

