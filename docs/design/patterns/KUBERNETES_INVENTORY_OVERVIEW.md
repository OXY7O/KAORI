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

The summary includes total objects, populated asset categories, and largest inventory segment. The final Operational Context section explains that the data is a committed database snapshot and provides one state-aware next step.

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
