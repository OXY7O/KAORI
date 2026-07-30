# Kubernetes Inventory Overview Pattern

## Reference Implementation

```text
app/templates/inventory/overview/
```

## Canonical Composition

```text
Canonical Hero
Inventory Data Snapshot
Inventory Asset Catalog
Compact Cluster Inventory Table
└── View Details → Right-Side Drawer
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

Uses `snapshot_context_bar.html` and owns:

- committed source;
- semantic snapshot state;
- exact latest collection time;
- active scope;
- committed coverage;
- stale and missing snapshot exceptions.

### Inventory Asset Catalog

Contains Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, and Configuration. Cluster is not an inventory asset and does not appear as an asset card.

### Compact Cluster Inventory Table

Canonical columns:

```text
Cluster | Connection | Total Objects | Last Snapshot | Inventory Signals | Details
```

Asset-level counts belong in the detail drawer, not in the comparison row.

### Detail Drawer

Uses the shared Side Drawer content primitives and contains:

- Cluster Snapshot Summary;
- Cluster Identity;
- Snapshot Context;
- Inventory Breakdown;
- Inventory Signals;
- Operational Context;
- `Open Cluster Inventory` action.

The summary includes total objects, populated asset categories, and largest inventory segment. The final Operational Context section explains that the data is a committed database snapshot and provides one state-aware next step.

## Data Contract

- all counts use the current committed inventory generation;
- per-cluster counts use grouped aggregate queries, not one query per cluster and asset;
- Healthy means connected and collected within the freshness window;
- normal freshness is not repeated as an Inventory Signal;
- signals represent only conditions requiring awareness;
- state-aware drawer guidance distinguishes disconnected, never-collected, stale, signalled, and current snapshots.

## Pagination

- default 5;
- options 5, 10, 25, 50;
- visible `Rows` label;
- resource-aware copy such as `Showing 1–3 of 3 Clusters`;
- section-owned loading bar;
- pagination replaces only table content.
