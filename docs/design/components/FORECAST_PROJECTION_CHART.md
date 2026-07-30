# KAORI Forecast Projection Chart Standard

## Purpose

`forecast_projection_chart.html` is the shared historical and projected utilization visualization for Kubernetes Dashboard and Kubernetes Analytics.

## Shared ownership

The component owns:

- SVG grid and plotting geometry;
- warning and critical threshold lines;
- historical solid-line and projected dashed-line semantics;
- canonical resource stroke mapping;
- current/historical and horizon axis labels;
- legend geometry;
- approved 10 px chart microcopy.

Pages provide normalized series points, horizon, historical availability, and an accessible label. Pages must not copy the SVG or axis classes.

## Resource mapping

- CPU: Info semantic family;
- Memory: KAORI Violet;
- Storage: Normal semantic family;
- Pods: Pending semantic family;
- unknown series: muted content color.

## Usage

```jinja
{% import "components/forecast_projection_chart.html" as forecast_chart %}

{{ forecast_chart.render(
    dashboard.forecast_snapshot.series,
    dashboard.forecast_snapshot.horizon_days,
    has_historical_series=dashboard.forecast_snapshot.has_historical_series,
    aria_label='Historical and projected Kubernetes resource utilization'
) }}
```

## Rules

- Keep interpretation, risk status, and recommendations outside the chart component.
- Do not turn threshold legend values into status badges.
- The chart remains readable without relying on color alone through solid/dashed line semantics and text labels.
