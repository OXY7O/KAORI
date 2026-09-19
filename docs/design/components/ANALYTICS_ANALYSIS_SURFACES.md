# Analytics Analysis Surface Standard

Status: Canonical KAORI Analytics presentation contract

Implementation: `app/templates/analytics/components/_analysis_surfaces.html`

## Purpose

Analytics pages have different evidence, but they must read as one product. Capacity is the reference composition. Resource Utilization, Capacity, Workload, Storage, Forecast, Top Consumers, Alerts, and Analytics Overview use the same shell, header, metric, evidence, and guidance grammar without forcing every domain into the same layout.

## Baseline Composition

1. One calm `rounded-xl` analysis shell.
2. One compact header with icon, Title Case title, semantic status, short description, and at most one drill-down action.
3. One peer metric strip when the domain has summary metrics.
4. Neutral evidence and context regions with role-colored compact anchors.
5. Neutral interpretation, decision, attention, and recommended-action regions whose icon and eyebrow label express Brand, Insight, Evidence, or Status role.

Use:

- `snapshot_shell_classes()`
- `snapshot_header_classes()`
- `snapshot_header_icon_classes()`
- `metric_grid_classes(columns)`
- `metric_cell_classes()`
- `evidence_shell_classes(...)`
- `context_panel_classes(...)`
- `interpretation_grid_classes(...)`
- `guidance_card_classes(...)`
- `interpretation_callout(...)`
- `interpretation_content(...)`

The previous Overview-only surface component was removed. Do not introduce a compatibility wrapper or duplicate page-local surface macros.

## Primary Evidence

Controls, readiness, committed snapshot metadata, charts, ranked records, pressure lanes, findings, and analytical context use neutral `bg-surface-card` or `bg-surface-muted` surfaces. Borders and whitespace separate peer evidence. Role-colored compact icons, labels, badges, charts, and bars provide hierarchy without tinting complete evidence panels.

## Interpretation and Attention

Interpretation, recommended action, review path, decision guidance, and attention use neutral card surfaces with subtle outlines or separators. A compact icon and eyebrow label express the assigned visual role. Attention may also carry one semantic Warning or Critical badge.

All operator guidance is rendered through the canonical callout contract documented in `ANALYTICS_OVERVIEW_GUIDANCE_STANDARD.md` and the role system in `ANALYTICS_VISUAL_ROLE_SYSTEM.md`. `interpretation_callout(...)` owns the wrapper and spacing. `interpretation_content(...)` supplies the same role-aware icon-led hierarchy inside an existing record, side panel, or pressure lane.

## Resource Pressure Lane

Implementation: `app/templates/kubernetes/analytics/components/_resource_pressure_lane.html`

The lane includes resource identity, semantic status, current percentage, used/capacity, progress, headroom, and operational reading. Use it for Utilization Summary, Utilization Node Detail, and other analytics pages that need the same pressure evidence.


## Analytics Overview Composite Loading Exception

Analytics Overview may add one compact composite progress strip because its tracked requests belong to one workspace and expose determinate section completion. Every tracked section keeps its local loading state. The composite strip reports completed or failed requests, resets with Overview filter changes, and hides after completion. This exception does not authorize a global loading bar across unrelated analytics pages or dashboard domains.

## Heavy Tab Loading

Summary and lightweight action lists may render with the page. Heavy evidence such as historical charts or node-specific analysis loads when its tab is first activated. Hidden tabs must not poll. A pending heavy tab may poll only after activation and must stop when the committed snapshot replaces the pending fragment.

## Multi-Series Chart Legend

Implementation: `app/templates/kubernetes/analytics/components/_chart_legend.html`

Every multi-series chart with the native Chart.js legend disabled must render a compact visible legend using the same semantic/CSS tokens as the plotted series.

## Unavailable Metric State

Missing analytical evidence is not a zero value. Use semantic `Unknown`, display `N/A` for measured values, suppress progress visualization, and provide a short evidence-restoration message. Do not render `0.0%` for an unavailable denominator.

## Semantic Progress Ownership

Progress color follows meaning. Status-bearing utilization, pressure, risk, and headroom bars use semantic green, amber, red, or slate through `progress_bar.semantic_bar(...)`. Composition, contribution, ranking, loading, and materialization bars remain KAORI Violet. The surrounding evidence lane remains neutral.

## Evidence Record Collection

Implementation: `app/templates/kubernetes/analytics/components/_evidence_record_list.html` and `app/templates/kubernetes/analytics/components/_record_filter_bar.html`.

Use this pattern for record-oriented analytical evidence with desktop columns, responsive mobile labels, semantic state, local filtering, and server pagination. The owning panel remains bright. Filters and pagination update only that panel, retain a full-page URL, and use the global 5/10/25/50 page-size contract.

## Extended Record Filter Bar

Record-oriented Analytics panels may expose a calm primary filter row and a closed-by-default Advanced Filters region through `analytics/kubernetes/components/_record_filter_bar.html`. Keep Search and the most frequently used dimensions visible. Put secondary configuration dimensions and Reset inside Advanced Filters. The region may open initially only when an advanced filter is active.

## Analytics Evidence Coverage

A workload or record-level recommendation that depends on multiple observations must declare evidence coverage as `Complete`, `Partial`, or `Unavailable`. Only Complete evidence may activate automatic right-sizing. Partial evidence produces review guidance; Unavailable evidence renders `Unknown`/`N/A` and suppresses derived progress.

## Mixed-Scope Analytics

When one workspace combines datasets with different Kubernetes scopes, every panel must name its effective scope. A selector must be placed at the narrowest owner that applies to all evidence it changes. Do not place a Node selector in a top filter when Namespace and PV panels do not consume that selector.

## Prohibited Patterns

- No Overview-only compatibility wrapper.
- No duplicated shell, header, metric, tone, or pressure-lane geometry in page templates.
- No inline multi-hundred-line chart scripts inside Jinja templates.
- No polling while a heavy tab is hidden.
- No full Brand, Insight, or semantic tint around primary charts, metrics, ranked data, pressure evidence, or ordinary guidance.

## Analytics Projection Configuration

Forecast-like workspaces may group controls into Scope and Projection Configuration inside one shared controls/readiness shell. This is a semantic grouping with a divider, not nested cards. Resource tabs own resource navigation; a resource selector must not duplicate those tabs.

## Forecast Evidence Semantics

Forecast primary evidence uses Latest Daily Average, Projected Horizon Value, Weekly Trend, and Historical Signal Quality. Signal Quality describes history completeness and stability, not model accuracy. Mixed namespace/cluster denominators must be named in each resource panel.

Full-page interactive forecast charts use the shared tokenized chart contract and tab-visible lifecycle. Compact dashboard charts retain the shared SVG component.

## Ranked Consumer Evidence and Shared Record Pagination

Top Consumers and future consumer-oriented workspaces use `analytics/kubernetes/components/_ranked_evidence_panel.html` for rankings. Consumption, contribution, denominator pressure, and configuration state remain separate signals. Mixed-resource pages never sort raw CPU, bytes, and counts as one numeric domain.

All record-oriented Analytics domains use `analytics/components/_record_pagination.html`. Domain-local pagination partials are prohibited. Full-page `href` and owning-partial HTMX endpoints must be explicit. Expanded record details are closed by default and include a native `hidden` fallback across HTMX swaps.

## Alerts & Anomalies Signal Evidence

Alerts & Anomalies follows `ANALYTICS_ALERTS_ANOMALIES.md`. Source readiness and committed snapshot evidence remain separate. Optional anomaly, routing, silence, or inhibition gaps produce `Evidence Incomplete` or a limited semantic state; they never produce Healthy by absence. Alerts and Anomalies records use the shared evidence collection and record pagination, while routing, suppression, ownership, and readiness evidence remain neutral and their interpretation or recommended action uses the shared role-aware guidance composition.

