# Kubernetes Inventory Overview Styling Audit — July 2026

## Decision Package

Approved and implemented:

- A1 — reusable Inventory Asset Catalog;
- B1 — remove duplicated supporting metric row;
- C1 — canonical compact Inventory Data Snapshot;
- D2 — Compact Cluster Inventory Table with `View Details` drawer;
- remove sync, freshness, and coverage duplication from the hero;
- enrich the cluster drawer with summary, condition explanations, data boundary, and state-aware guidance.

## Removed Drift

- page-local hero posture markup;
- hero-level last-sync and freshness duplication;
- non-clickable mixed Cluster/asset KPI grid;
- duplicated coverage, freshness, healthy-target, and average-object cards;
- wide eleven-column cluster matrix;
- `Risk Hints` terminology and duplicated `Fresh Sync` label;
- page-local snapshot-bar typography;
- flat drawer sections without reusable content geometry;
- per-cluster N+1 resource count queries.

## Shared Owners

```text
components/snapshot_context_bar.html
components/inventory_asset_card.html
components/side_drawer.html
```

## Resulting Page Structure

```text
Hero — fleet posture only
Compact Inventory Data Snapshot — source, time, scope, coverage, exceptions
Eight-Asset Catalog
Compact Cluster Table
Cluster Detail Drawer
```

## Drawer Contract

The drawer follows this order:

```text
Cluster Snapshot Summary
Identity + Snapshot Context
Inventory Breakdown
Inventory Signals
Operational Context
```

Operational Context is always placed at the bottom. It states that data comes from the latest committed database snapshot and provides one next action based on connection, collection age, and active inventory signals.

## Data Semantics

Healthy cluster posture requires both:

- connected cluster state; and
- a committed snapshot within the configured freshness window.

Grouped aggregate queries collect counts per asset model for all clusters. The previous count-query loop per cluster remains prohibited.

## Drawer Readability Refinement

Cluster detail uses concise section headers, compact identity/snapshot cards without redundant descriptions, and a divided plain-metric summary row. Technical values follow normal detail typography unless an explicit raw-copy monospace exception is requested.
