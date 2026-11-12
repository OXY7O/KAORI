# Kubernetes Inventory Overview Pattern

## Reference Implementation

```text
app/templates/kubernetes/inventory/overview/
```

## Canonical Composition

```text
Canonical Hero
Inventory Data Snapshot
Inventory Asset Catalog
Compact Cluster Inventory Table
└── View Details → Full Workspace Modal · Unified Resource Sheet V10
```

## Cross-domain Inventory Overview reuse

Kubernetes remains the reference implementation for committed Inventory Overview semantics. Other inventory domains reuse the same hierarchy primitives without cloning Kubernetes data semantics.

Where a domain has meaningful committed fleet-level posture beyond freshness, retain both the shared Inventory Asset Catalog and fleet evidence sections. Domain-specific ordering and metric content may differ; the **Object Storage 2026-11-12 human UAT** requires the Kubernetes Operations Overview presentation sequence:

```text
Canonical Hero
Inventory Data Snapshot
Inventory Assets — Section Intro
└── Object Storage Asset Catalog — operational_section_card
    ├── 2 Asset Types — committed scope badge
    └── Systems / Buckets & Containers — compact workspace_link_card navigation
Fleet Inventory Posture — Section Intro
└── Object Storage Fleet Evidence — operational_section_card
    ├── 4 Indicators — committed metric count badge
    └── inset bordered resource_posture_grid (4 committed readings)
```

The **approved cross-domain grammar** is the shared `components/section_intro.html` heading, the owning `operational_section_card.html`, and compact content padding/borders. Under #4421 the Kubernetes Operations Overview is the exact visual reference: its **Operation Workspace Catalog** comes before **Execution & Evidence Model**, with 40px Violet destination icons and compact footer links; the second card places its three steps inside a padded, bordered grid. For Object Storage, the first section likewise displays the catalog before the evidence block. The Fleet card retains **four** provider-neutral, committed metrics (quota/protection/exposure/optional usage), now inside the shared posture grid's **opt-in `compact=true`** layout. **Human UAT clarification (#4427):** the screenshot reference requires the actual **Execution & Evidence Model** tile composition, not only its inset border. The compact variant owns the same rounded, bordered, gap-pixel grid, uniformly Violet 32px identity icons, compact heading, and **one** supporting line. Each metric's committed value appears as the leading semantically colored inline part of that supporting line, followed by its original source-qualified description; warning, critical and unknown values remain visually distinguishable. There is **no separate oversized KPI value row** in compact mode. Four values remain four columns at desktop widths because the Object Storage source has four independent signals, whereas Kubernetes' execution model has three steps. The default `resource_posture_grid` rendering for other Inventory/Registry consumers remains unchanged. No Kubernetes mutation workflow is invented and metric values are never repurposed as execution steps.

The two Object Storage catalog destinations reuse the exact `components/workspace_link_card.html` **compact=true** navigation renderer already used by Kubernetes Operations. The existing committed asset catalog still supplies title, icon, description, exact endpoint and CTA; the top-right scope badge derives `N System(s)` or `N Asset(s)` from the committed counts rather than hiding them. Its footer keeps the domain action label (Browse Systems/Browse Buckets & Containers) through the optional `workspace.action_label` fallback; existing Kubernetes/Welcome workspace cards still render **Open Workspace** by default. This replaces the earlier `inventory_asset_card(..., compact_count=true)` Object Storage visual-only experiment, restoring the original shared inventory asset card defaults for other consumers.

**Artifact Registry Inventory Human UAT alignment (#4455, 2026-11-12):** The operator's latest Registry screenshot explicitly requests the **already approved Object Storage Inventory Overview** composition, superseding #946's older Registry Fleet-first/default large-count-card exception. Registry Inventory Overview now renders its existing committed Snapshot context, then **Inventory Assets → Registry Asset Catalog**, followed by **Fleet Inventory Posture → Registry Fleet Evidence**, using `section_intro` and one owning `operational_section_card` for each group. The Catalog's three Projects/Repositories/Artifacts navigation destinations now use the same existing `workspace_link_card(..., compact=true)` renderer as Object Storage/Kubernetes Operations; current committed counts become dynamically derived top-right metadata scope badges with correct singular/plural names, and original URLs, Browse labels, provider-neutral descriptions and focus semantics are preserved. The Fleet uses the existing **three** committed provider/snapshot/project-visibility readings in `resource_posture_grid(columns=3, compact=true)`, a shared Violet governance-style inset panel and a static `fleet_posture_metrics|length ~ ' Indicators'` label (**3 Indicators** for current readings). No fourth signal, provider call or invented security evidence is introduced.

On the Registry **Projects**, **Repositories** and **Artifacts** Inventory submenus, the dedicated Operational Posture section keeps its **four** domain-owned metrics and default `resource_posture_grid(columns=4)`; the card header now displays the static Violet `resource_posture_metrics|length ~ ' Indicators'` badge (**4 Indicators** for each current submenu), following Object Storage Systems/Namespaces. This is **not** a new title Guide popover: existing Registry inventory **table-title** Guide controls remain intact because they explain column semantics and provider evidence boundaries.

**Registry Inventory posture and detail microcopy UAT refinement (#4455, 2026-11-12):** The four metric descriptions in each Projects/Repositories/Artifacts Operational Posture card use compact, source-qualified sentences intended to fit one desktop line without forcing `nowrap` or truncating on smaller screens. Provider participation, public visibility, missing visibility, pull-count and tag evidence remain distinct; metric counts, status tones and underlying committed queries are unchanged. Registry Project/Repository/Artifact detail modals reuse the existing Kubernetes Inventory compact `detail.workspace_header(..., context_items=..., compact=true)` and `detail.inventory_title(..., compact=true)` patterns. Provider/repository/project metadata belongs to the header context row, while Project Visibility remains a separate semantic status. All detail sections continue to use the shared `detail.resource_sheet` / `detail.inventory_section` components, but their left-rail descriptions are brief and domain-specific (identity, provider/environment, coverage, timing, and snapshot scope). Table evidence, provider native fields, statuses, timestamps, original modal footer, and authoritative committed snapshot source remain unchanged. These are responsive copy and composition refinements only, not a new modal implementation or provider clone.

Kubernetes Inventory retains Snapshot → Asset Catalog → Cluster Inventory Table. Provider-neutral counts, no-evidence/unknown conditions, source-of-truth semantics, actions and actual inventory routes remain unchanged. On Object Storage Systems/Namespaces pages, existing static metadata badges remain `metrics|length ~ ' Indicators'`, never Guide popovers. The scoped Registry revision reuses existing shared components and requires real desktop/mobile, light/dark, keyboard and screenshot-based Human Acceptance.

The Object Storage visual correction is bounded to section order, shared compact navigation and metric layout. No provider request, data model, worker, API, authorization, mutation, pagination, freshness classification or new CSS/JS style family is introduced. Responsive wrapping and light/dark contrast follow shared Violet components.

Consistency applies to reading order and shared primitives, not to forcing identical metrics or equal card counts across domains.

## Ownership

### Hero

Owns fleet identity and high-level posture only:

- registered clusters;
- inventory asset-type count;
- collected-object total;
- connected-cluster posture;
- exceptional inventory-signal count;
- `Manage Clusters` action.

The hero does not show last sync, freshness percentage, freshness window, or committed coverage.

### Inventory Data Snapshot

Uses the compact `snapshot_context_bar.html` pattern between the hero and asset catalog. It owns:

- committed source;
- semantic snapshot state;
- exact latest collection time;
- active scope;
- committed coverage;
- stale and missing snapshot exceptions.

The component remains one compact neutral context row. The identity block and four transparent metrics share one surface, with subtle dividers instead of nested Violet metric cards. Semantic color is limited to the status label and meaningful coverage/exception icons. It does not become a second hero or a multi-row KPI section.

### Inventory Asset Catalog

Contains Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, and Configuration. Cluster is not an inventory asset and does not appear as an asset card.

### Compact Cluster Inventory Table

Canonical columns:

```text
Cluster | Connection | Total Objects | Last Snapshot | Inventory Signals | Details
```

Asset-level counts belong in the detail modal, not in the comparison row.

### Cluster Detail Modal

Uses `components/resource_detail_modal.html` and Unified Resource Sheet V10 primitives and contains:

- Cluster Snapshot Summary;
- Cluster Identity;
- Snapshot Context;
- Inventory Breakdown;
- Inventory Signals;
- Operational Context;

The summary includes total objects, populated asset categories, and largest inventory segment. Inventory Breakdown reuses the shared section metadata badge to display `N/8 Types` from the committed nonzero asset-category count; this is an inventory-composition count, not collection completeness or healthy posture. The Inventory Breakdown subtitle stays concise: `Committed objects by resource type.` The final Operational Context section explains that the data is a committed database snapshot and provides one state-aware next step.

The four section subtitles should remain compact and usually fit one desktop line: Cluster Identity — `Cluster name, version, connection.`; Snapshot Context — `Collection, source, freshness.`; Inventory Breakdown — `Committed objects by resource type.`; Inventory Signals — `Collection and operational signals.` Keep natural wrapping on narrow screens rather than enforcing `whitespace-nowrap`. For a current committed snapshot with no active signals, the state-aware action description is `Snapshot current; no active signals. Review assets.`; disconnected, stale, incomplete, and signalled branches retain their distinct meanings.

## Data Contract

- all counts use the current committed inventory generation;
- per-cluster counts use grouped aggregate queries, not one query per cluster and asset;
- Healthy means connected and collected within the freshness window;
- normal freshness is not repeated as an Inventory Signal;
- signals represent only conditions requiring awareness;
- state-aware detail guidance distinguishes disconnected, never-collected, stale, signalled, and current snapshots.

## Pagination

- default 5;
- options 5, 10, 25, 50;
- visible `Rows` label;
- resource-aware copy such as `Showing 1–3 of 3 Clusters`;
- section-owned loading bar;
- pagination replaces only table content.

## Detail Readability Refinement

Cluster detail uses the shared full-workspace modal, one connected summary strip, and one Unified Resource Sheet. Identity, snapshot, breakdown, and signal evidence share the same horizontal-band geometry and calm proportional typography. The modal body is the single vertical scrolling context.

Every metric in **Cluster Snapshot Summary** must preserve the same three-level
hierarchy: label, primary value, and concise supporting text. `Total Objects` uses
`Committed Objects`, `Asset Categories` uses `Collected Categories`, and `Largest
Segment` uses the dominant segment count. Do not leave one metric visually shorter
than its peers.

## Snapshot Source and Signal Layout

- The drawer uses the concise source label `Committed Snapshot`, rendered with `detail_row(..., nowrap=True)`, so `Snapshot Source` stays horizontally aligned with `Last Collected` and `Freshness Window`.
- Inventory Signals are rendered as full-width stacked callouts. Each additional signal starts on the next row; signal cards are not placed side by side.


## Collection Coverage and Connection State

A fresh `ClusterInventory.collected_at` timestamp does not establish a complete
inventory observation. Fleet health, snapshot context, row signals, and detail
guidance must distinguish fully `Collected` family evidence from partial, failed,
or absent `collection_evidence`. Unknown connection status means `Not Observed`,
not a confirmed disconnection. A zero asset count without a committed snapshot
is not proof that zero objects were collected. All readings are committed-state
only and use existing KAORI semantic labels.


## Bounded Cluster Comparison and Modal Reads

Overview comparison uses canonical SQL pagination (5/10/25/50) **before**
materializing its per-cluster detail-ready row projections. Exact global fleet
counts and active signal counts still use grouped committed aggregate evidence;
only page clusters become full cluster detail records. The Cluster detail endpoint
projects exactly one committed cluster and its current resource-family counts,
without invoking a full Overview projection. Table-only HTMX and modal fragments
do not re-query the Snapshot Context Bar, while full page and workspace renders
retain committed freshness context. Scope, RBAC and canonical modal stay intact.


### Fleet total query reuse

The Overview's eight committed-generation `GROUP BY cluster_id` resource
count maps are also the authoritative fleet-level totals: sum each resource
family's grouped counts once, rather than issuing eight duplicate COUNT queries.
This preserves exact global totals while paging the cluster detail projection
via the canonical SQL pagination contract. It does not change query freshness
or the actual count of returned Kubernetes provider objects.
