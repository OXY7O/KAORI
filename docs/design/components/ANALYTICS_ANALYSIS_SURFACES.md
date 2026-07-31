# Analytics Analysis Surface Standard

Status: Canonical KAORI Analytics presentation contract

Implementation: `app/templates/analytics/components/_analysis_surfaces.html`

## Purpose

Analytics pages have different evidence, but they must read as one product. Capacity is the reference composition. Resource Utilization, Capacity, Workload, Storage, Forecast, Top Consumers, Alerts, and Analytics Overview use the same shell, header, metric, evidence, and guidance grammar without forcing every domain into the same layout.

## Baseline Composition

1. One calm `rounded-xl` analysis shell.
2. One compact header with icon, Title Case title, semantic status, short description, and at most one drill-down action.
3. One peer metric strip when the domain has summary metrics.
4. Bright evidence and context regions.
5. Darker soft interpretation, decision, attention, or recommended-action regions.

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

The previous Overview-only surface component was removed. Do not introduce a compatibility wrapper or duplicate page-local surface macros.

## Primary Evidence

Controls, readiness, committed snapshot metadata, charts, ranked records, pressure lanes, findings, and analytical context use `bg-surface-card`. Borders and whitespace separate peer evidence. Do not use a dark fill for primary data.

## Interpretation and Attention

Use `bg-surface-hover` only for interpretation, recommended action, review path, decision guidance, or attention. An attention strip also carries a semantic Warning or Critical cue.

## Resource Pressure Lane

Implementation: `app/templates/analytics/components/_resource_pressure_lane.html`

The lane includes resource identity, semantic status, current percentage, used/capacity, progress, headroom, and operational reading. Use it for Utilization Summary, Utilization Node Detail, and other analytics pages that need the same pressure evidence.


## Analytics Overview Composite Loading Exception

Analytics Overview may add one compact composite progress strip because its tracked requests belong to one workspace and expose determinate section completion. Every tracked section keeps its local loading state. The composite strip reports completed or failed requests, resets with Overview filter changes, and hides after completion. This exception does not authorize a global loading bar across unrelated analytics pages or dashboard domains.

## Heavy Tab Loading

Summary and lightweight action lists may render with the page. Heavy evidence such as historical charts or node-specific analysis loads when its tab is first activated. Hidden tabs must not poll. A pending heavy tab may poll only after activation and must stop when the committed snapshot replaces the pending fragment.

## Multi-Series Chart Legend

Implementation: `app/templates/analytics/components/_chart_legend.html`

Every multi-series chart with the native Chart.js legend disabled must render a compact visible legend using the same semantic/CSS tokens as the plotted series.

## Unavailable Metric State

Missing analytical evidence is not a zero value. Use semantic `Unknown`, display `N/A` for measured values, suppress progress visualization, and provide a short evidence-restoration message. Do not render `0.0%` for an unavailable denominator.

## Semantic Progress Ownership

Progress fills remain KAORI Violet unless a domain-specific visualization contract explicitly says otherwise. Healthy, Warning, and Critical meaning belongs to semantic labels, icons, and operational copy rather than recoloring the entire evidence lane.

## Evidence Record Collection

Implementation: `app/templates/analytics/components/_evidence_record_list.html` and `app/templates/analytics/components/_record_filter_bar.html`.

Use this pattern for record-oriented analytical evidence with desktop columns, responsive mobile labels, semantic state, local filtering, and server pagination. The owning panel remains bright. Filters and pagination update only that panel, retain a full-page URL, and use the global 5/10/25/50 page-size contract.

## Extended Record Filter Bar

Record-oriented Analytics panels may expose a calm primary filter row and a closed-by-default Advanced Filters region through `analytics/components/_record_filter_bar.html`. Keep Search and the most frequently used dimensions visible. Put secondary configuration dimensions and Reset inside Advanced Filters. The region may open initially only when an advanced filter is active.

## Analytics Evidence Coverage

A workload or record-level recommendation that depends on multiple observations must declare evidence coverage as `Complete`, `Partial`, or `Unavailable`. Only Complete evidence may activate automatic right-sizing. Partial evidence produces review guidance; Unavailable evidence renders `Unknown`/`N/A` and suppresses derived progress.

## Mixed-Scope Analytics

When one workspace combines datasets with different Kubernetes scopes, every panel must name its effective scope. A selector must be placed at the narrowest owner that applies to all evidence it changes. Do not place a Node selector in a top filter when Namespace and PV panels do not consume that selector.

## Prohibited Patterns

- No Overview-only compatibility wrapper.
- No duplicated shell, header, metric, tone, or pressure-lane geometry in page templates.
- No inline multi-hundred-line chart scripts inside Jinja templates.
- No polling while a heavy tab is hidden.
- No `bg-surface-hover` around primary charts, metrics, ranked data, or pressure evidence.
