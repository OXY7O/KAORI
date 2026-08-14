# KAORI Forecast Projection Chart Standard

## Purpose

KAORI provides two forecast chart compositions with one semantic contract:

- compact SVG chart for Kubernetes Dashboard and Analytics Overview;
- interactive Chart.js chart for the full Resource Forecast workspace.

## Compact Chart

Implementation: `components/forecast_projection_chart.html`.

The compact chart owns SVG geometry, thresholds, historical/projected line semantics, canonical resource mapping, axis labels, and approved chart microcopy. It is intended for summary surfaces.

## Interactive Chart

Implementation:

- `analytics/kubernetes/components/_interactive_forecast_chart.html`
- `static/js/analytics/kubernetes/forecast_chart.js`

The interactive chart owns tooltip behavior, long history rendering, combined resource comparison, visible textual legends, and hidden-tab lifecycle management.

## Shared Resource Mapping

- CPU: Info semantic family.
- Memory: KAORI Violet.
- Storage: Normal semantic family.
- Pods: Warning/Pending semantic family.
- Warning threshold: Warning semantic family.
- Critical threshold: Critical semantic family.

JavaScript resolves CSS variables. Raw page-local hex palettes are prohibited.

## Line Semantics

- historical evidence: solid line;
- projected evidence: dashed line;
- warning threshold: semantic dashed line;
- critical threshold: semantic dashed line.

A visible text legend is required when the native chart legend is disabled. The visualization must remain interpretable without relying on color alone.

## Lifecycle

Interactive charts render only when the owning panel is visible and measurable. Use the shared analytics tab-visible event, double animation-frame stabilization, bounded retry, and `ResizeObserver`. Click-delay hydration is prohibited.

## Rules

- Keep interpretation, risk status, scope boundary, and recommendations outside the chart component.
- Do not turn threshold legend values into status badges.
- Do not copy chart geometry or color maps into page templates.
- Compact and interactive charts must use the same terminology and resource mapping.
