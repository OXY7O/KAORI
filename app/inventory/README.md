# Kubernetes inventory domain

Inventory stores normalized Kubernetes resource snapshots and presents resource
identity and relationships consistently across clusters.

## Boundaries

- `collectors/` reads Kubernetes APIs and normalizes resource payloads.
- `persistence.py` writes one inventory generation atomically.
- `synchronization.py` owns collection orchestration and commits the generation marker.
- `resources/` owns read use cases for lists, filter options, summaries, details, and SQL pagination.
- `routes.py` handles HTTP/HTMX concerns and validates request filters.
- `topology/` owns relationship-map construction and presentation.

All-cluster views use database snapshots. Do not introduce hidden live Kubernetes
API calls into list, summary, detail, or topology pages.

## Committed-generation invariant

`ClusterInventory.collected_at` is the committed generation marker for a cluster.
Every read of a generation-scoped inventory model must pass through
`filter_current_generation`, including:

- table rows and summary aggregates;
- dependent filter options;
- detail drawers and related-object counts;
- overview totals and per-cluster counts;
- topology nodes and relationships.

This prevents an incomplete, stale, or superseded generation from being mixed with
the active snapshot. `Cluster` and `ClusterInventory` themselves are not filtered by
this helper because they define cluster identity and the generation marker.

## HTMX filter scope

Resource filters replace the complete `*-inventory-scope` block. The scope contains
both summary cards and the table card so totals always describe the active filters.
Pagination replaces only `*-table-content`; it must not rebuild filter options or
summary cards. Resource services must use `app.common.pagination.paginate_query`
so only the requested ORM rows are materialized. Summary cards may use lightweight
filtered projections, but routes must never call `.all()` and slice the full result.
A cluster change must rebuild dependent namespace, status, type, role, owner, node,
or class options from the same committed generation.

## Consistency rules

Inventory pages use the same filter, pagination, label, empty-state, and detail
patterns. Default page size is 5 with 5/10/25/50 options. Keep raw payloads and
technical exceptions out of rows; expose only relevant normalized information.
Topology relationships must come from the latest committed snapshot and preserve
Cluster and Namespace boundaries.

Workload Pod configuration is authoritative only when supplied by the workload
collector's schema-v2 `pod_template`. Do not infer configuration from runtime Pods;
a missing template is an explicit unavailable state and requires a fresh sync.

## Template data access

When a template receives a dictionary key whose name overlaps a Python mapping method,
such as `items`, `keys`, or `values`, use bracket access (`payload['items']`). Dot
access can resolve to the mapping method and produce a runtime iterable error.

## Inventory Presentation Consistency

All resource inventory pages use the shared KAORI table block, loading bar, filter controls, and row-action components. Filter changes replace the complete inventory scope so summary metrics, dependent filter options, and table rows remain synchronized. Pagination replaces table content only. Resource detail actions remain compact neutral actions, while semantic labels use the global status-label mapping.

### Cross-Resource Visual Contract

- Overview and resource summaries use one bordered data block with internal metric cells; do not reintroduce independent decorative cards.
- Resource-name columns use `text-sm` with optional muted supporting text. Namespaced resource tables use the shared compact Namespace identity icon with semibold text; overview rows keep the icon only in the Cluster identity column.
- Table row actions use `components/table.html`; semantic labels are compact `rounded-md` labels, never pills. Inventory row labels default to text-only, with tone carrying status meaning instead of decorative icons.
- Resource type, quota, and Pod Security values use plain table text when descriptive. Workload update strategy uses a compact text-only semantic label: Rolling Update is Normal, Recreate is Warning, On Delete is Info, and unknown strategies use Unknown.
- Inventory loading indicators use `components/loading_bar.html` and sit directly beneath the block header.
- List services must not compute related-object counts that are not rendered in the current table. Related composition belongs in the detail endpoint.

### Reusable Interaction Contract

- Page-size selectors use the shared `data-kaori-auto-submit` behavior implemented in `app/static/js/pagination.js`; do not add inline `onchange` handlers.
- Long key/value metadata that cannot safely share one row uses `components/detail_object.html::stacked_row`, with the key above the value and explicit wrapping.
- Detail rows use `components/details/_expandable_row.html` and `app/static/js/detail_rows.js`; page-specific inline toggle scripts are not permitted.
- Title Case applies to user-facing inventory metadata labels while Kubernetes identifiers and canonical resource names retain their original casing.
- Remove page-specific partials after their callers migrate to shared components; do not retain unreferenced compatibility templates.


## Presentation Contracts

- Inventory row identity icons are reserved for Cluster identity, shared Namespace identity, and section-level context. Workload, Pod, owner, role, status, condition, label, and annotation values remain text-only unless an icon materially improves identification.
- Phase and readiness are separate evidence. Pod operational state uses Ready, Starting, Not Ready, Failed, Completed, or Unknown. Restart counts remain cumulative factual values unless a time-windowed signal exists.
- Kubernetes labels and annotations use compact wrap-safe text labels without decorative icons. Long annotation values must wrap inside the card boundary.
- Image pull policy, QoS, restart policy, DNS policy, host network, security-context presence, selectors, and tolerations remain factual evidence until an explicit governance policy evaluates them. Volume type is metadata and runtime state remains semantic.
- Topology detail status values are normalized to Title Case before presentation.


### Table and Detail Typography

- Node capacity identity values (Internal IP, CPU, Memory, and Storage) use semibold primary text for fast operational scanning.
- Namespace Resource Quota and Pod Security values use semibold text, while their detailed Resource Controls content expands naturally without an internal scroll area.
- Workload and Pod namespace cells reuse the Namespace identity icon without converting the namespace into a semantic badge.
- Primary workload and Pod operational values use semibold typography; semantic state labels retain their status color.
- Semantic and metadata badges inside View More summary cards use the same 12px type scale as adjacent detail labels and values. Table badges retain the compact 10px scale.
- Decorative icons are omitted from placement values, Host Network state, node-selector values, and section-count labels when the text already provides sufficient meaning. Associated-resource timelines center connector lines on their status markers.

- Service, Ingress, Storage, and Configuration tables use the shared Namespace identity treatment. Type/count fields remain plain or semantic text according to their operational meaning, without decorative icons.
- Semantic labels remain for lifecycle/status states only, and use tone without decorative icons unless an icon materially improves comprehension.

### Canonical Inventory Page Composition

- Inventory Overview and every resource page use `components/page_hero.html::context_card` for the right-side hero posture. Do not rebuild hero metrics, status badges, or the Manage Clusters action with page-local markup. Inventory Overview keeps exact sync, freshness, and coverage values out of the hero because `snapshot_context_bar.html` owns that context.
- Resource summary blocks use `inventory/components/_summary.html`. The component owns the summary header, four primary metrics, one progress metric, and two supporting status metrics.
- Resource table cards use `components/table.html::inventory_block_header`, canonical filter labels/controls, and canonical table/head/body/row classes. Page templates remain responsible only for filter fields and route parameters.
- View More cards use `components/details/_detail_content.html` for card geometry, rows, metadata rows, and status rows. Local copies of `detail_card`, `detail_row`, `metadata_row`, or `status_row` are not permitted.
- Summary, table, and detail components must remain presentation-only. They must not query data, infer resource state, or own HTMX endpoints.

### Namespace Identity and Title-Case Presentation

- Every namespaced resource table uses the shared `table_ui.namespace_identity(...)` macro. The macro owns the compact Namespace icon, semibold typography, truncation, and empty fallback for Namespace cells across Namespace, Workload, Pod, Service, Ingress, Storage, and Configuration Inventory.
- Human-facing table headers, detail-card titles, field labels, empty-state titles, status descriptions, and topology detail labels use Title Case. Kubernetes identifiers, annotation keys, label keys, resource names, API values, and controller-specific values remain unchanged.
- Ingress annotation entries render the annotation key above its value so long controller annotations such as `kubectl.kubernetes.io/last-applied-configuration` remain readable without compressing either field into a side-by-side grid.

## Inventory Overview Reference Pattern

The Inventory Overview is the canonical reference for fleet-level inventory composition:

```text
Canonical Hero
Compact Inventory Data Snapshot
Inventory Asset Catalog
Compact Cluster Inventory Table
View Details → Side Drawer
```

- Asset catalog cards use `components/inventory_asset_card.html` and link to Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, and Configuration.
- Cluster is a collection scope/provider, not an asset card.
- Snapshot source, exact time, active scope, committed coverage, and stale/missing exceptions use `components/snapshot_context_bar.html`.
- The cluster comparison table remains compact. Asset counts belong in the `components/side_drawer.html` detail view. The drawer uses shared section and metric primitives, ends with Operational Context, and provides one state-aware next action.
- Cluster posture is Healthy only when the target is connected and its committed snapshot is inside the freshness window.
- Per-cluster overview counts must use grouped aggregates across the selected clusters. Do not reintroduce one count query per cluster and asset type.


## Kubernetes Topology Reference Pattern

Topology uses Visualization Workspace Style 1 (`adaptive-explorer`) through `components/visualization_workspace.html`. On `2xl` it presents persistent Controls, Canvas, and Inspector panes; below `2xl`, Controls and Details become adaptive drawers so the visualization keeps primary width.

Graph / Resource List and Details / Relationships use Tab Style 2 (`compact-segmented`) through `components/segmented_tabs.html`. Resource List is the keyboard-accessible representation and remains available from the committed payload if Cytoscape cannot load. Exact snapshot time and coverage remain owned by the shared Inventory Data Snapshot, not the hero.

Topology colors use the five-domain token set in `frontend/styles.css`: Scope, Compute, Networking, Configuration, and Storage. Operational health remains a separate semantic status dot. Page templates and JavaScript do not define raw palette values.

`app.inventory.topology.service.build_topology_graph` caches payloads by committed-generation signature and normalized filters, conditionally queries only resource families needed by scope/depth, and indexes Service/Pod matching by cluster and namespace.

## Node Inventory Reference Pattern

Node Inventory is the canonical implementation of the per-resource inventory page pattern:

```text
Canonical Hero → Snapshot Context → Node Resource Posture → Compact Table → Full Workspace Modal
```

The compact table groups Node identity, cluster, readiness, role, capacity, and network evidence. Role is metadata, readiness is operational status, and technical identifiers use the shared Technical Value component. Detail requests remain on demand and read the latest committed generation; they do not query the Kubernetes API live.

- Readable topology nodes use compact domain badges with one-line external name labels, bounded ellipsis, and quiet containment connectors. Full names and resource types remain available in Resource List and Details.
- Inventory detail drawers use concise section descriptions and proportional technical value typography by default.


## Namespace Inventory Reference Pattern

Namespace Inventory follows the canonical per-resource page composition:

```text
Canonical Hero → Snapshot Context → Namespace Control Posture → Compact Table → Full Workspace Modal
```

Lifecycle transition, resource controls, and security configuration are factual inventory evidence. `Terminating` is informational until stuck-transition evidence exists. Missing quota, LimitRange, NetworkPolicy, or PSA labels do not imply a compliance failure without an explicit governance policy. Labels and annotations use `technical_metadata_collection.html`.

## Workload Inventory presentation

Workload Inventory follows the canonical Inventory Resource Page Pattern. The hero owns delivery and runtime posture, the posture grid owns workload composition and exceptions, and the compact table separates semantic operational state from controller-specific evidence. Associated Pods use the shared Related Resource Collection. Workload configuration is factual evidence until an explicit governance policy evaluates it.

### Inventory detail density and Rows behavior

Namespace and Workload details use the shared Adaptive Detail Stacks contract from `components/details/_detail_content.html`. Natural-height cards replace equal-height rows when evidence volumes differ. The Node, Namespace, and Workload Rows selectors refresh their owning inventory scope so the selected page size remains synchronized with subsequent filter requests. Resource filter forms must use local bubbled `change` handling rather than a global `from:select` listener.

## Pod Inventory Reference Pattern

Pod Inventory is the fourth Inventory Resource Page reference. It uses Pod Runtime Posture, a compact grouped table, Adaptive Detail Stacks, Container Runtime Collection, reference-only Related Resource Collection rows, and Technical Metadata Collection. Pod page-size changes refresh `#pods-inventory-scope`, and owner type constrains available Phase and Node filters.

## Service and Ingress presentation

Service and Ingress Inventory use the canonical Inventory Resource Page pattern. Service backend evidence is EndpointSlice-first with Endpoints fallback. Ingress backend references are resolved from committed Service Inventory. Network publication, TLS references, traffic policy, and controller class remain factual evidence until an explicit governance policy evaluates them.

Expanded details use natural-height Adaptive Detail Stacks. Evidence tiles must not create empty gray cells, metadata collections avoid nested vertical scrolling, and ordinary table technical values use the same body typography as adjacent values.

## Storage and Configuration reference implementations

Storage Inventory uses type-adaptive provisioning, capacity/access, and binding/lifecycle evidence. StorageClass configuration is factual; PV/PVC lifecycle carries semantic state.

Configuration Inventory uses protected key-index metadata. Values are not decoded, logged, persisted, or displayed. ConfigMap and Secret collection capability is stored on `ClusterInventory.collection_evidence` for the committed generation.

Node through Configuration Inventory use `Detail Style 2 — Full Workspace Modal`, owned by `components/resource_detail_modal.html`, `components/details/_detail_content.html`, and `app/static/js/detail_rows.js`. Inventory Overview retains the shared Side Drawer, and Topology retains the Adaptive Explorer Inspector.

## PostgreSQL JSON relationship queries

Pod labels, configuration references, and PersistentVolumeClaim references are stored through SQLAlchemy JSON columns. PostgreSQL relationship filters must cast these columns to `JSONB` before calling `.contains(...)` so SQL compiles to JSON containment (`@>`) rather than text `LIKE`.

Canonical examples:

```python
cast(PodInventory.labels, JSONB).contains(selector)
cast(PodInventory.persistent_volume_claims, JSONB).contains([claim_name])
```

Non-PostgreSQL development environments use bounded Python matching fallbacks. Do not call `.contains()` directly on the generic JSON columns for PostgreSQL-backed Inventory detail queries.

## Full Workspace Modal text wrapping

Inventory detail evidence must remain readable without intentional truncation. The shared modal supports a 100 rem maximum width, hides horizontal page overflow, and lets technical metadata, relation identities, hostnames, labels, annotations, selectors, and multi-line values wrap with `overflow-wrap:anywhere`. Metadata collections do not use nested vertical scrolling.
