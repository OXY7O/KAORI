# KAORI Operational Dashboard Pattern

## Purpose

This pattern defines a read-only, snapshot-backed operational dashboard that combines scope, KPIs, integrated tabs, tables, charts, and visible action guidance without creating page-local styling systems.

## Canonical composition

```text
Canonical Hero
Scope and Freshness Toolbar
Operational KPI Grid
Tab Style 1 — Integrated Workspace Tabs
├── Primary Operational Sections
├── Full-Width Complex Tables
└── Equal-Height Peer Content Grid
```

## Rules

- Web requests read committed database or worker snapshots only; styling changes must not weaken the data boundary.
- Keep hero geometry canonical and avoid duplicate freshness metadata.
- Use `operational_metric_card.html` for KPI cards.
- Use Tab Style 1 (`integrated-workspace`) through `workspace_tabs.html`; tabs attach to the workspace and do not become a separate card.
- Persist the active tab in the URL.
- Use `operational_section_card.html` for repeated block shells.
- Use `peer_content_grid.html` when both dashboard blocks are primary tab content.
- Peer boxes stretch to the tallest box in the row.
- Use `context_rail.html` only when the right side is genuinely secondary supporting context.
- Use `operational_flow_steps.html` for static action or response flow boxes inside peer main content. Supporting tips may follow the flow through `operational_callout.html` and remain visible.
- Use `forecast_projection_chart.html` for historical/projected resource visuals.
- Use canonical tables, labels, states, pagination, and resource-aware copy.
- Initial asynchronous sections use local skeleton placeholders. Tables with in-place pagination or filtering also use a section-owned loading bar.
- Avoid card-inside-card composition, duplicate actions, and expandable primary flows.

## Reference implementation

`app/templates/dashboards/kubernetes/partials/_content.html` is the first canonical implementation.
