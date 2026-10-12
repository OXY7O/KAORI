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

Where a domain has meaningful committed fleet-level posture beyond freshness, the approved extension is:

```text
Canonical Hero
Inventory Data Snapshot
Fleet Inventory Posture
<Domain> Asset Catalog
```

The overview uses `components/section_intro.html` for the outer section hierarchy.
Following explicit human DevContainer review under #946, **Artifact Registry and Object Storage** both use the existing grouped-summary Fleet standard: `section_intro` → one `operational_section_card` → `resource_posture_grid`, without additional per-metric cards. Registry has three committed provider/snapshot/visibility metrics; Object Storage preserves all four committed quota/protection/exposure/optional-usage readings, in a responsive two/four-column grid. Each metric keeps its evidence tone and supporting text, and a fleet with no committed bucket/container evidence displays `No Evidence` instead of a fabricated zero/healthy posture. Both catalogs use `Inventory Assets` as the outer section intro and one intentional standard Asset Catalog container with a shared count badge and `inventory_asset_card` links. Object Storage has Systems and Buckets & Containers (two asset types); Registry has Projects, Repositories, and Artifacts (three). Navigation continues to read existing committed-state counts and routes. This current visual authority supersedes the earlier Object Storage flat-callout/flat-catalog instruction in #946; domain metrics are intentionally not forced to be identical. Kubernetes intentionally continues with Snapshot → Asset Catalog → Cluster Inventory Table because its fleet comparison is owned by the cluster table rather than a duplicate posture section.

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

The summary includes total objects, populated asset categories, and largest inventory segment. The Inventory Breakdown subtitle stays concise: `Committed objects by resource type.` The final Operational Context section explains that the data is a committed database snapshot and provides one state-aware next step.

The four section subtitles should remain compact and usually fit one desktop line: Cluster Identity — `Cluster registration, version, and connection.`; Snapshot Context — `Collection time, source, freshness, and state.`; Inventory Breakdown — `Committed objects by resource type.`; Inventory Signals — `Collection and operational signals.` Keep natural wrapping on narrow screens rather than enforcing `whitespace-nowrap`. For a current committed snapshot with no active signals, the state-aware action description is `Snapshot current; no active signals. Review assets.`; disconnected, stale, incomplete, and signalled branches retain their distinct meanings.

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
