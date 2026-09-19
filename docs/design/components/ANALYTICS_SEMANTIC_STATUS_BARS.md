# Analytics Semantic Status Bars

## Purpose

A bar that communicates status must not remain violet when its semantic state is Normal, Warning, Critical, Unknown, or Info. The bar fill must match the adjacent badge and operational interpretation.

## Canonical ownership

`app/templates/components/progress_bar.html` owns:

- semantic tone normalization;
- semantic fill classes;
- high-is-risk pressure thresholds;
- low-is-risk headroom thresholds;
- high-is-good score thresholds;
- the `semantic_bar(...)` renderer.

Domain templates supply a semantic tone or a factual value. They do not choose color classes directly.

## Audited status bars

- Utilization overview, trend, and node filesystem pressure
- Capacity utilization, allocation, resource pressure, and headroom risk
- Storage overview, node filesystem records, aggregate PVC utilization, and PVC records
- Workload tenant quota pressure and per-resource request utilization
- Forecast projected utilization
- Alerts ownership coverage, incident readiness, and severity distribution

## Deliberate violet exceptions

These bars are factual progress or composition, not health assertions:

- analytics materialization progress;
- HTMX/loading indicators;
- Top Consumers contribution to scope;
- ranked evidence contribution share;
- Alert receiver and namespace distributions.

Changing those bars to semantic colors would incorrectly imply operational health.
