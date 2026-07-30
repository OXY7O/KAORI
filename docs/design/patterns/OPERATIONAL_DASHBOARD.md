# KAORI Operational Dashboard Pattern

## Purpose

This pattern defines a read-only, snapshot-backed operational dashboard that combines scope, KPIs, peer workspace tabs, tables, charts, and contextual guidance without creating page-local styling systems.

## Canonical composition

```text
Canonical Hero
Scope and Freshness Toolbar
Operational KPI Grid
Standalone Workspace Tabs
├── Primary Operational Sections
├── Full-Width Complex Charts or Tables
└── Peer Content Grid for primary content pairs
```

## Rules

- Web requests read committed database or worker snapshots only; styling changes must not weaken the data boundary.
- Keep hero geometry canonical and avoid duplicate freshness metadata.
- Use `operational_metric_card.html` for KPI cards.
- Use `workspace_tabs.html` and persist the active tab in the URL.
- Use `operational_section_card.html` for repeated block shells.
- Use `peer_content_grid.html` when both dashboard blocks are primary tab content.
- Use `context_rail.html` only when the right side is genuinely secondary supporting context.
- Use `forecast_projection_chart.html` for historical/projected resource visuals.
- Use canonical tables, labels, states, and pagination.
- Avoid card-inside-card composition and duplicate actions.
- Initial asynchronous dashboard sections use skeleton placeholders. Do not attach one global loading bar to unrelated dashboard regions.

## Reference implementation

`app/templates/dashboards/kubernetes/partials/_content.html` is the first canonical implementation.
