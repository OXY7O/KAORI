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
└── Main Content + 20rem Context Rail where guidance is secondary
```

## Rules

- Web requests read committed database or worker snapshots only; styling changes must not weaken the data boundary.
- Keep hero geometry canonical and avoid duplicate freshness metadata.
- Use `operational_metric_card.html` for KPI cards.
- Use `workspace_tabs.html` and persist the active tab in the URL.
- Use `operational_section_card.html` for repeated block shells.
- Use `context_rail.html` when a primary block needs secondary readiness, guidance, or a related workspace.
- Use `forecast_projection_chart.html` for historical/projected resource visuals.
- Use canonical tables, labels, states, and pagination.
- Avoid card-inside-card composition and duplicate actions.

## Reference implementation

`app/templates/dashboards/kubernetes/partials/_content.html` is the first canonical implementation.
