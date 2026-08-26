# KAORI Analytics XLSX Design

**Status:** Implemented contract; Analytics XLSX enabled in the report catalog  
**Date:** 2026-08-26  
**Scope:** Kubernetes Analytics and Object Storage Analytics Excel artifacts

## Goal

Add Analytics XLSX as an analysis artifact without reusing the Inventory workbook structure as a generic template. PDF remains the management publication; XLSX becomes the drill-down, filtering, trend, and evidence workbook. Analytics XLSX must reuse the global KAORI XLSX presentation system while owning an analytics-specific workbook contract.

## Contract hierarchy

- Global format contract: `kaori-reporting-xlsx-v2.0`.
- Inventory workbook contract remains `kaori-inventory-xlsx-v4.0`.
- Analytics workbook contract: `kaori-analytics-xlsx-v1.0`.
- The report catalog remains authoritative and now enables XLSX for published Analytics report types while retaining PDF as the default format.

## Category ownership

Analytics XLSX is generated per primary analytics category. KAORI must not create one oversized workbook that combines every analytics domain.

### Kubernetes Analytics

1. Analytics Overview
2. Resource Utilization
3. Capacity
4. Storage
5. Workload
6. Forecast
7. Top Consumers
8. Alerts & Anomalies

### Object Storage Analytics

1. Analytics Overview
2. Capacity Usage
3. Performance
4. Growth & Forecast
5. Consumer Analytics
6. Alerts & Anomalies

The report catalog owns the exact enabled report types. A category can be omitted until its collector and publication contract are complete.

## Shared workbook pattern

Every Analytics XLSX begins with `Overview` and ends with `Metadata` and `Field Dictionary`. Intermediate sheets are category-owned and may include:

- `Analysis`
- `Trends`
- `Breakdown`
- `Top Consumers`
- `Alerts & Anomalies`
- `Recommendations`
- `Raw Data`

A sheet is present only when the category has committed evidence for that semantic surface. Do not add empty decorative sheets merely to make workbooks look consistent.

## Overview contract

The Analytics Overview is executive-oriented but evidence-preserving:

1. title, report purpose, selected asset, period, and data cut-off;
2. four domain-owned KPI cards;
3. concise evidence-derived Executive Readout;
4. up to three semantic visuals appropriate to the category;
5. compact insight cards where the backend already owns the signal semantics;
6. Workbook Navigation.

The renderer never invents health conclusions, forecasts, alerts, or recommendations. It presents committed analytics evidence only.

## Visual semantics

- Analytics Overview forecast posture uses a clustered Current vs Projected resource bar; resource-level forecast records must never be reinterpreted as time-series points;
- ordered time-series evidence uses line charts;
- ranked consumers use horizontal ranked bars with direct labels and Supporting Data;
- status or part-to-whole evidence uses compact doughnut/100% composition visuals only when the denominator is meaningful;
- capacity comparisons use used/headroom or requests/limits/usage visual semantics owned by the profile;
- forecast workbooks plot committed historical and forecast series, but Excel must not calculate the forecast itself;
- alert visuals summarize committed severity/state evidence and never duplicate Alert Intelligence workflow state.

## Recommendations

A `Recommendations` sheet is allowed only when the Analytics collector already supplies KAORI recommendations. The XLSX renderer must not generate new recommendations at export time. Published fields should include priority, recommendation, evidence, affected resource, expected outcome, and source rule when available.

## Data transparency

Every visual must have inspectable source rows in a category data sheet or `Raw Data`. Excel is a presentation and analysis artifact, not a second analytics engine. Calculations that define KAORI analytics remain backend-owned so PDF, XLSX, UI, and API outputs share the same denominator and model result.

## Navigation and presentation

Analytics XLSX reuses KAORI Violet, Aptos/Aptos Display, typed cells, bounded widths, freeze panes, native Excel tables, formula-injection protection, internal navigation, grouped Metadata, Field Dictionary, and post-save artifact validation from the global XLSX standard.

## Implementation gate

Analytics XLSX remains enabled only while implementation provides:

1. analytics workbook schema/profile model;
2. category-specific sheet contracts;
3. shared Overview renderer;
4. time-series/ranked/composition chart contracts;
5. runtime artifact validator;
6. regression tests for every enabled analytics category;
7. parity checks against the same canonical analytics payload used by PDF/CSV;
8. worker restart/deployment guidance because report generation executes outside the web request process.
