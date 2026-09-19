# Kubernetes Analytics Design Consistency & Runtime Audit

Date: 2026-07-28  
Scope: KAORI Kubernetes Analytics

## Objective

Audit the Kubernetes Analytics pages against the established KAORI visual and interaction standard, remove inconsistent or duplicated presentation patterns, and verify that HTMX, Alpine, materialized snapshot, table, filter, tab, and error-state behavior remain operational.

## Pages Reviewed

- Kubernetes Analytics Overview
- Resource Utilization
- Capacity Analysis
- Storage Analysis
- Workload Analysis
- Resource Forecast
- Top Consumers
- Alerts & Anomalies
- Shared analytics materialization and readiness components

## Executive Findings

The analytics pages had accumulated several independent redesign and hotfix patterns. Most individual pages were visually close to the KAORI standard, but the shared boundaries were inconsistent. This created repeated code, hidden runtime risks, and different behavior for tabs, filters, loading indicators, errors, and large record lists.

The consolidation patch standardizes the shared contracts first and then aligns page-specific content with those contracts.

## Critical Runtime Findings

### 1. Shared Prometheus macro signature mismatch

`_analysis_workspace.html` invoked:

```jinja2
prometheus_status_panel.render(status, checked_at, flat=true, compact=true)
```

The Prometheus macro did not originally accept `flat` or `compact`. Any page entering that shared controls path could fail during Jinja rendering.

**Resolution:** the shared Prometheus macro now explicitly supports both parameters and safely handles absent status fields.

### 2. Alerts anomaly result contract was consumed incorrectly

`load_prometheus_anomaly_metrics()` returns:

```python
(anomaly_rows, anomaly_source_status)
```

The alert application treated the tuple as the anomaly row list. This could break filtering or cause incorrect anomaly presentation.

**Resolution:** the tuple is unpacked explicitly. Optional Prometheus anomaly failure now produces a visible partial-data warning while preserving Alertmanager records.

### 3. Utilization trend presentation had no trend summary producer

The Trend Analysis template expected `trend_summary`, but the materialization context did not build it. The page therefore fell back to empty/default summary values even when trend series were available.

**Resolution:** added `build_utilization_trend_summary()` and included the result in the trend context. It calculates current, average, peak, sample count, peak resource, and overall posture.

### 4. Tab runtime was not consistently attached

Some pages rendered shared tab buttons without a standard `data-analytics-tabset` boundary. The generic JavaScript controller could not reliably resolve the owning tabset after HTMX swaps.

**Resolution:** Overview, Alerts, Top Consumers, Utilization, Capacity, Storage, Workload, and Forecast now use the same native tab runtime and Alpine progressive enhancement contract.

## KAORI Standard Applied

### Controls & Data Readiness

The shared workspace now consistently provides:

- page-specific filters;
- local KAORI loading bar;
- Prometheus status;
- latest committed snapshot;
- dataset key;
- last update;
- refresh due time;
- worker attempt;
- stale snapshot notice;
- source evidence warning;
- latest refresh error.

Prometheus status is no longer duplicated as a separate box above filters on pages using the shared controls component.

### Tabs and content

- Tabs are integrated into the content workspace.
- Tabs wrap instead of forcing horizontal scrolling.
- Active tab state is stored per page and per tabset.
- Native `hidden` state prevents all panels from appearing during delayed Alpine hydration.
- HTMX swaps rehydrate the generic tab controller.
- Arrow Left, Arrow Right, Home, and End keyboard navigation remain supported.
- Tab changes do not write URL hashes or move the viewport.

### Filters and HTMX

- Analytics filter forms use automatic HTMX updates.
- Every HTMX filter form has a local loading indicator.
- Every HTMX filter form has an `hx-sync` replacement boundary.
- Broad cross-form event selectors were removed where they could trigger unrelated filters.
- Table filters update only the relevant table or result fragment.

### Large records and tables

The following large sections were converted to responsive operational rows instead of forced-width tables:

- Detected Anomaly Candidates
- Node Filesystem Usage
- Persistent Storage
- Tenant Quota Analysis
- Workload Resource Mapping

This removes nested horizontal scrolling and keeps actions usable on smaller screens.

### Expandable content

Overview recommendation expanders using `<details>/<summary>` were removed. Operational recommendations are presented as compact static rows. View Details remains only where row-level detail genuinely benefits from progressive disclosure.

### Semantic styling

Direct Tailwind palette utilities such as red, amber, green, blue, and cyan were removed from the audited analytics templates. Semantic KAORI tokens are used for normal, warning, critical, info, disabled, and unknown states.

### Error presentation

A reusable `_status_notice.html` component was added for consistent warning and critical messages. Capacity, Storage, and Workload use the same visual error boundary instead of independent banner implementations.

## Page Review Summary

| Page | Audit result | Main consolidation |
|---|---|---|
| Analytics Overview | Standardized | Tabs integrated with content; recommendation expanders removed; HTMX sections synchronized |
| Resource Utilization | Standardized and runtime fixed | Shared readiness; stable tabs; local trend/node loading; computed trend summary |
| Capacity Analysis | Standardized | Shared readiness; stable tabs; common status notice; prior dictionary `items` collision remains fixed |
| Storage Analysis | Standardized | Shared readiness; responsive filesystem/PV/PVC records; local pagination loading |
| Workload Analysis | Standardized | Shared readiness; responsive quota/mapping records; compact recommendations |
| Resource Forecast | Reviewed as compliant | Existing compact overview, charts, legends, readiness, and stable tabs retained |
| Top Consumers | Standardized | Shared readiness component; generic tab runtime; persistent Consumer Detail loading boundary |
| Alerts & Anomalies | Standardized and runtime fixed | Stable tab/swap boundaries; responsive anomalies; partial-data warnings; local filters/loading |

## Dead Code and Duplication Removed

- Top Consumers-specific tab stabilizer replaced by the shared analytics tab controller.
- Repeated controls/readiness markup replaced with shared macros.
- Repeated error boxes replaced with one status notice component.
- Legacy Overview recommendation expanders removed.
- Redundant forced-width table wrappers removed.

## Validation Performed

- Python compilation of changed Python modules: passed.
- JavaScript syntax:
  - `analytics_controls.js`: passed.
  - `analytics_forecast.js`: passed.
- Jinja parsing: 91 analytics templates passed.
- Strict shared Controls & Data Readiness render: passed.
- Analytics contract suite: 94 passed.
- Automated audit:
  - no `<details>` or `<summary>`;
  - no `overflow-x-auto` in analytics templates;
  - no inline `style=`;
  - no direct red/amber/green/blue/cyan Tailwind utilities;
  - all HTMX forms have `hx-indicator` and `hx-sync`.

## Validation Limitation

A full Flask application and browser end-to-end run could not be executed in the sandbox because Flask is not installed. The final deployment validation should therefore include route rendering and browser interaction in the KAORI Dev Container.

## Recommended Deployment Verification

1. Open every Kubernetes Analytics page and confirm HTTP 200.
2. Change clusters quickly several times and confirm the latest choice remains active.
3. Change each page filter and confirm only the intended workspace updates.
4. Open every tab and confirm only one panel is visible.
5. Test search, page size, numeric pagination, Previous, and Next.
6. Confirm local loading bars appear without triggering unrelated page indicators.
7. Stop or overload the Prometheus test endpoint and confirm the UI shows a clear provider or snapshot error rather than empty healthy data.
8. Confirm Alertmanager alerts remain available if optional Prometheus anomaly collection fails.
9. Confirm Resource Utilization Trend displays current, average, and peak values from committed trend data.
