# Analytics Resource Forecast Standard

Status: Canonical KAORI Analytics domain contract
Updated: 2026-08-06

Implementation:

- `app/analytics/kubernetes/forecast/contracts.py`
- `app/analytics/kubernetes/forecast/calculation.py`
- `app/analytics/kubernetes/forecast/presentation.py`
- `app/analytics/kubernetes/forecast/resource.py`
- `app/analytics/kubernetes/forecast/service.py`
- `app/analytics/kubernetes/forecast/routes.py`
- `app/templates/analytics/kubernetes/forecast/index.html`
- `app/templates/analytics/kubernetes/forecast/partials/_hero.html`
- `app/templates/analytics/kubernetes/forecast/partials/_controls_readiness.html`
- `app/templates/analytics/kubernetes/forecast/partials/_overview_methodology.html`
- `app/templates/analytics/kubernetes/forecast/partials/_forecast_section.html`
- `app/templates/analytics/kubernetes/components/_interactive_forecast_chart.html`
- `app/static/js/analytics/kubernetes/forecast_chart.js`

## Purpose

Resource Forecast converts committed Prometheus history into capacity-planning evidence for CPU, memory, storage, and active Pods. It is a planning signal. It does not authorize autonomous remediation or replace live-state verification before a capacity decision.

## Evidence Boundary

CPU, memory, and Pods use one Ready-worker boundary:

- exclude `control-plane` and legacy `master` roles;
- include only nodes with `Ready=true`;
- compare workload demand with Ready-worker allocatable capacity;
- normalize duplicate container, Pod, and node series before aggregation;
- count active Pods in `Pending|Running`.

Storage uses mounted-volume evidence:

- usage: `kubelet_volume_stats_used_bytes`;
- denominator: `kubelet_volume_stats_capacity_bytes`;
- duplicate series: `max by(namespace,persistentvolumeclaim)` before summation;
- terminology: Observed Volume Capacity, never requested claim capacity.

Namespace forecasts retain the same denominator contract. Namespace CPU, memory, and Pod demand are compared with cluster Ready-worker allocatable capacity. Namespace PVC usage is compared with Namespace Observed Volume Capacity.

## Materialization Identity

The committed dataset key is `analytics.forecast`.

Provider-query dimensions:

- `cluster_id`;
- `history_window`;
- `namespace` when selected.

Presentation-only dimensions:

- `forecast_horizon`;
- `method`;
- `tab`.

Presentation-only dimensions re-project committed history locally and must not create new worker jobs or snapshot fingerprints. Supported history windows are `7d`, `30d`, and `90d`. Query profiles therefore declare `required_history='90d'` so the longest supported window is validated.

## Forecast Models

Canonical models:

- **Holt-Winters** — default; evaluates level, trend, and weekly additive seasonality.
- **Linear Trend** — simple comparison baseline.
- **Conservative Trend** — preserves the Holt-Winters seasonal shape and applies a 15% uplift only to positive projected growth.

The removed Moving Average implementation must not return as an alias or compatibility wrapper.

## Status and Threshold Semantics

Canonical thresholds:

- Normal: below 75%.
- Warning: 75% to 89.9%.
- Critical: 90% or above.

Resource status is based on the **highest projected point inside the selected horizon**, not only the endpoint. The endpoint remains visible as supporting evidence.

Threshold ETA is derived by walking the actual projected points from the latest historical observation. It is bounded by the selected horizon:

- `Reached` when the latest observation already crosses the threshold;
- `N days` when a projected point crosses within the horizon;
- `Beyond <horizon>d horizon` when no crossing occurs inside the selected horizon;
- `N/A` when evidence or capacity is unavailable.

Do not extrapolate an unbounded ETA from a linear slope and present it as part of the selected horizon.

## Signal Quality and Posture

Historical Signal Quality evaluates sample count, date completeness, and variation. It is not model confidence or a claim of forecast accuracy.

Planning-ready signal quality:

- High;
- Medium.

Low signal quality is **Limited Evidence**, even when the projected percentage is below the warning threshold. Aggregate posture states:

- Critical Projection;
- Capacity Watch;
- Limited Evidence;
- Within Capacity;
- Evidence Unavailable.

`Within Capacity` requires all four resources to be available and planning-ready, with no warning or critical projection.

## Unavailable Evidence

A resource forecast requires at least two daily samples and a positive capacity baseline. When unavailable:

- status is Unknown;
- values display `N/A`;
- progress is suppressed;
- threshold ETA displays `N/A`;
- the chart is replaced by an evidence-restoration state;
- the resource is excluded from highest-projection and warning/critical counts.

Missing observations remain `null` in charts. They must not be converted to zero, Normal, Stable, or Healthy.

## Workspace Composition

1. Shared KAORI hero with posture and scoped context.
2. Forecast Controls & Data Readiness.
3. Forecast Overview outside the tabs.
4. CPU, Memory, Storage, Pods, Trend Analysis, and Recommendations tabs.
5. Bright evidence surfaces for metrics and charts.
6. Darker guidance surfaces for interpretation and accountable action.

The controls contain:

- Scope: Cluster and Namespace.
- Projection Configuration: Model, History Window, and Forecast Horizon.

Resource navigation belongs to tabs. Do not add a Resource Focus selector that duplicates tab navigation.

## Interactive Chart

The combined chart uses the union of timestamps from every resource. Each series maps values to that common axis and preserves absent observations as `null`.

Required behavior:

- historical line: solid;
- projection line: dashed;
- warning and critical lines: semantic token colors;
- y-axis: dynamic `suggestedMax`, never a fixed 100% ceiling;
- native Chart.js legend: disabled;
- visible textual legend: mandatory;
- initialization only after the tab is visible and measurable;
- `ResizeObserver` and HTMX lifecycle support.

Chart payload is held in a non-executable `<template data-kaori-json-payload>`. Do not add an inline executable script or page-local color palette.

## Route Boundary

`/analytics/forecast` is the only Forecast workspace route. The removed `/analytics/kubernetes/forecast/section` fragment endpoint had no active consumer and must not return.

The full page may be replaced through standard HTMX navigation, but Forecast does not maintain a duplicate page-specific fragment route.

## Code Ownership

- `contracts.py` — options, thresholds, resource definitions, value objects.
- `calculation.py` — model calculation, quality, ETA, posture, chart payload.
- `service.py` — Prometheus orchestration and committed snapshot construction.
- `resource.py` — resource evidence, status, ETA, and serialization.
- `presentation.py` — snapshot adapter and local model/horizon/tab projection.
- `routes.py` — full-page materialized transport boundary.
- Jinja — rendering only.

Do not move domain thresholds, forecast status, ETA, or chart alignment logic back into Jinja.

## Reports

Forecast report payload and PDF publication consume the same committed evidence and canonical 75%/90% thresholds. Report exposure status uses peak projected percentage. Data cut-off must come from the committed snapshot timestamp. Missing resource evidence remains explicitly Not Available.

## Recommendation Routing

Recommendations deep-link to the owning resource tab or Trend Analysis. Links preserve Cluster, Namespace, Model, History Window, and Forecast Horizon. Low signal quality routes to evidence validation before capacity commitment.

## Direct Cutover

Removed legacy surfaces:

- `app/static/js/analytics_forecast.js`;
- `app/templates/analytics/kubernetes/forecast/partials/_methodology.html`;
- `/analytics/kubernetes/forecast/section` and endpoint `analytics.forecast_section`.

Do not add wrappers, fallback imports, Resource Focus aliases, Moving Average aliases, confidence-field aliases, or a duplicate Forecast fragment route.
