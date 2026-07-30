# Kubernetes Inventory Overview Pattern

## Reference Implementation

```text
app/templates/inventory/overview/
```

## Canonical Composition

```text
Canonical Hero
Snapshot Context Bar
Inventory Asset Catalog
Compact Cluster Inventory Table
└── View Details → Right Side Drawer
```

## Ownership

### Hero

Owns fleet posture, high-level coverage/freshness, collected-object total, and `Manage Clusters`.

### Snapshot Context Bar

Owns exact source, collection timestamp, active scope, and committed coverage. It must not duplicate an asset metric grid.

### Inventory Asset Catalog

Contains Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, and Configuration. Cluster is not an inventory asset and does not appear as an asset card.

### Compact Cluster Inventory Table

Canonical columns:

```text
Cluster | Connection | Total Objects | Last Snapshot | Inventory Signals | Details
```

Asset-level counts belong in the detail drawer, not in the comparison row.

### Detail Drawer

Contains:

- Cluster Identity;
- Inventory Breakdown;
- Snapshot Context;
- Inventory Signals;
- `Open Cluster Inventory` action.

## Data Contract

- all counts use the current committed inventory generation;
- per-cluster counts use grouped aggregate queries, not one query per cluster and asset;
- Healthy means connected and collected within the freshness window;
- normal freshness is not repeated as an Inventory Signal;
- signals represent only conditions requiring awareness.

## Pagination

- default 5;
- options 5, 10, 25, 50;
- visible `Rows` label;
- resource-aware copy such as `Showing 1–3 of 3 Clusters`;
- section-owned loading bar;
- pagination replaces only table content.
