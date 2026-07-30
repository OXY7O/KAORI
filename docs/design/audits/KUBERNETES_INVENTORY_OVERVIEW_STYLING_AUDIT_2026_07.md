# Kubernetes Inventory Overview Styling Audit — July 2026

## Decision Package

Approved and implemented:

- A1 — reusable Inventory Asset Catalog;
- B1 — remove duplicated supporting metric row;
- C1 — canonical Snapshot Context Bar;
- D2 — Compact Cluster Inventory Table with `View Details` drawer.

## Removed Drift

- page-local hero posture markup;
- non-clickable mixed Cluster/asset KPI grid;
- duplicated coverage, freshness, healthy-target, and average-object cards;
- wide eleven-column cluster matrix;
- `Risk Hints` terminology and duplicated `Fresh Sync` label;
- page-local snapshot-bar typography;
- per-cluster N+1 resource count queries.

## New Shared Owners

```text
components/snapshot_context_bar.html
components/inventory_asset_card.html
components/side_drawer.html
```

## Resulting Page Structure

```text
Hero
Snapshot Context
Eight-Asset Catalog
Compact Cluster Table
Cluster Detail Drawer
```

## Table Contract

The table shows one row per registered cluster with connection, total objects, last committed snapshot, exceptional inventory signals, and one `View Details` action. The drawer exposes the complete eight-asset breakdown without increasing table width.

## Data Semantics

Healthy cluster posture now requires both:

- connected cluster state; and
- a committed snapshot within the configured freshness window.

Grouped aggregate queries collect counts per asset model for all clusters. The previous six-count-query loop per cluster has been removed.
