# Analytics Alerts Presentation Contracts

## Purpose

This Batch 3 slice narrows two broad internal dictionary boundaries without changing the dictionaries consumed by KAORI templates, dashboards, reports, or intelligence workflows.

The canonical contracts live in `app/analytics/alerts/contracts.py`:

- `AlertIntegrationStatus` and `AlertIntegrationStatusMap` describe Prometheus and Alertmanager connection presentation state;
- `AlertSourceHealthCheck` and `AlertSourceHealthSummary` describe source-health scoring and checks;
- `AlertRoutingGroup` and `AlertRoutingSummary` describe routing availability, counts, and grouped rows.

## Runtime Compatibility

All values remain ordinary `dict` and `list` objects. Existing keys, labels, CSS class strings, icons, scores, grouping order, and fallback semantics are unchanged.

The `class` key requires functional `TypedDict` syntax because it is a Python keyword. Source-health context fields (`selected_source`, `resolved_source`, and `fallback_used`) are intentionally optional because the no-cluster result preserves the existing smaller dictionary shape.

## Boundary Ownership

- `health.py` returns focused integration and source-health contracts.
- `routing.py` returns focused routing and grouped-row contracts.
- `AlertsSnapshot` references `AlertSourceHealthSummary` and `AlertRoutingSummary` directly instead of `dict[str, Any]`.
- `service.py` re-exports the contracts only as a temporary compatibility façade.

## Guardrails

Contract tests verify:

1. focused return annotations remain attached to health and routing builders;
2. snapshot annotations use the focused contracts;
3. functional and class-based `TypedDict` definitions are both discoverable;
4. runtime `__required_keys__` and `__optional_keys__` match existing dictionary shapes;
5. empty and populated routing/source-health results remain ordinary dictionaries.

## Non-Goals

This slice does not change source-health scoring, routing availability, grouping keys, receiver resolution, fallback behavior, or user-facing wording.
