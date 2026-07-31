# Analytics Resource Forecast Standard

Status: Canonical KAORI Analytics domain contract

Implementation:

- `app/templates/analytics/forecast/index.html`
- `app/templates/analytics/forecast/partials/_controls_readiness.html`
- `app/templates/analytics/forecast/partials/_overview_methodology.html`
- `app/templates/analytics/forecast/partials/_forecast_section.html`
- `app/templates/analytics/components/_interactive_forecast_chart.html`
- `app/static/js/analytics_forecast_chart.js`

## Purpose

Resource Forecast turns committed daily Prometheus history into capacity-planning evidence for CPU, memory, storage, and pods. It is an early planning signal, not an authoritative capacity commitment.

## Workspace Composition

1. Shared KAORI hero with exactly two context metrics and one bottom notice.
2. Forecast Controls & Data Readiness.
3. Forecast Overview outside the tabs.
4. Resource tabs for CPU, Memory, Storage, Pods, Trend Analysis, and Recommendations.
5. Bright primary metrics, capacity projection, charts, and resource outlook.
6. Darker interpretation and recommended-action regions.

Capacity remains the reference composition. Forecast may use domain-specific charts and threshold timing, but it does not reconstruct shell, metric, or interpretation geometry.

## Scope and Projection Configuration

The controls use two logical groups inside one shared controls shell:

- Scope: Cluster and Namespace.
- Projection Configuration: Model, History Window, and Forecast Horizon.

Resource navigation is owned by the workspace tabs. Do not add a Resource Focus selector that duplicates tab navigation.

Namespace semantics are explicit:

- CPU, Memory, and Pods: Namespace Demand vs Cluster Capacity.
- Storage: Namespace PVC Usage vs Namespace Claim Capacity.

Every resource panel names its scope, comparison, and capacity baseline.

## Forecast Models

Canonical model set:

- Holt-Winters — default. Evaluates level, trend, and weekly additive seasonality.
- Linear Trend — simple comparison baseline.
- Conservative Trend — applies a planning buffer to positive Holt-Winters growth.

The removed Moving Average implementation must not return as a compatibility alias.

## Factual Terminology

Use:

- Latest Daily Average, not Current Usage.
- Weekly Trend, not Growth Rate.
- Historical Signal Quality, not Forecast Confidence.
- Projected Horizon Value.

Historical Signal Quality evaluates sample count, completeness, and stability. It does not claim forecast accuracy or backtested model confidence.

## Unavailable Evidence

A forecast requires at least two daily samples and a non-zero capacity baseline. When unavailable:

- status is Unknown;
- values display N/A;
- progress is suppressed;
- threshold ETA displays N/A;
- the chart is replaced by an evidence-restoration state;
- unavailable resources are excluded from highest projection and warning/critical counts.

## Interactive Forecast Chart

Full Forecast pages use `analytics/components/_interactive_forecast_chart.html` and `analytics_forecast_chart.js`.

Canonical mapping:

- CPU: Info Blue.
- Memory: KAORI Violet.
- Storage: Normal Green.
- Pods: Warning Amber.

Historical lines are solid. Projection lines are dashed. Warning and Critical thresholds use semantic token colors. JavaScript resolves CSS variables and must not own page-local hex palettes.

The chart initializes only after its tab is visible and measurable. Required lifecycle:

- `kaori:analytics-tab-visible`;
- double animation frame;
- non-zero container dimensions;
- bounded retry;
- `ResizeObserver`;
- HTMX load, swap, and settle support.

The native Chart.js legend is disabled. A visible textual legend is mandatory.

## Recommendation Routing

Recommendations deep-link to the owning resource tab or Trend Analysis. Links preserve Namespace, Model, History Window, and Forecast Horizon. Missing evidence routes to the affected resource tab.

## Direct Cutover

The following legacy assets are removed:

- `app/static/js/analytics_forecast.js`
- `app/templates/analytics/forecast/partials/_methodology.html`

Do not add wrappers, fallback asset imports, Resource Focus aliases, Moving Average aliases, or confidence-field aliases.
