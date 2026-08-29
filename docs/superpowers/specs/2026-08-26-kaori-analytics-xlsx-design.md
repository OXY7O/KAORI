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

- Analytics Overview forecast posture uses a clustered Current vs Projected resource bar; resource-level forecast records must never be reinterpreted as time-series points.
- Ordered time-series evidence uses sparse line charts without dense point markers; percent trends use a 0–100 scale, 25-point major interval, and timestamps when committed timestamps exist.
- Ranked consumers use horizontal ranked bars limited to Top 8, one KAORI violet series, visible category labels, value-only direct labels, no redundant legend, and explicit value-axis headroom so labels do not collide with the chart edge. Long technical identities are shortened only on the chart (maximum 28 display characters); Supporting Data keeps the complete identity.
- Provider-native consumer values must be normalized to the committed display unit before charting or overview presentation. Memory byte values therefore become typed GiB values rather than raw bytes carrying a GiB suffix. XLSX consumer evidence uses one normalized numeric `Value` column plus `Unit`; raw/display duplicate columns are not part of the human analysis surface.
- Status or part-to-whole Analytics evidence uses a compact horizontal `composition_bar` with an explicit 0–100% denominator, semantic category colors, and percentage-only direct labels; doughnut rendering remains an Inventory concern rather than an Analytics dependency.
- Capacity comparisons use Utilization vs Headroom as complementary series over real resource/posture categories. `Used` and `Free` must not be emitted as separate pseudo-resources.
- Forecast workbooks plot committed historical and forecast series, but Excel must not calculate the forecast itself.
- Alert visuals summarize committed severity/state evidence and never duplicate Alert Intelligence workflow state. Unclassified records are shown explicitly when the severity denominator would otherwise be incomplete.
- Missing evidence such as `Not Available` is neutral/muted in evidence tables; it must never inherit a healthy/green semantic style merely because the text contains the word `available`.

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

## Implementation architecture and code-health refactor

Issue #13 may decompose the Analytics XLSX implementation, but it must not change the workbook contract above or the public export surface consumed by report generation and tests.

### Stable facade

`app/reports/export/xlsx/analytics_profiles.py` remains the compatibility facade for the existing Analytics XLSX profile API. Existing consumers must continue to resolve these public symbols without import-path changes:

- `ANALYTICS_WORKBOOK_PROFILES`
- `ANALYTICS_XLSX_REPORT_TYPES`
- `get_analytics_workbook_profile`
- `prepare_analytics_workbook_data`

The facade owns profile lookup and preparation dispatch only. It must not regain domain-specific normalization, row construction, chart-model construction, or report-family preparation logic after extraction.

### Internal ownership boundaries

The implementation is split by responsibility rather than by file length alone:

1. **Profile catalog** — declarative `AnalyticsWorkbookProfile` definitions and validation of profile metadata.
2. **Shared preparation support** — narrow normalization primitives and shared table/metric helpers used by multiple report families.
3. **Kubernetes preparers** — category-owned preparation for Resource Utilization, Capacity, Storage, Workload, Forecast, Top Consumers, Alerts & Anomalies, and Kubernetes Analytics Overview.
4. **Object Storage preparer** — Object Storage Analytics preparation and storage-unit normalization.
5. **Facade/dispatch** — stable report-type lookup and routing from canonical payload + `AnalyticsExportContext` to the selected preparer.

A helper belongs in shared support only when at least two preparers require the same semantic behavior. Helpers that encode one report family's meaning stay with that family. This prevents a new generic utility module from becoming the next oversized debt surface.

### Dependency direction

Internal dependencies are one-way:

- schema/types → shared preparation support;
- schema/types + shared support → category preparers;
- profile catalog + category preparers → `analytics_profiles.py` facade;
- workbook builders/renderers → facade/schema.

Category preparers must not import the facade, builder, validator, or renderer. Shared support must not import category preparers. This keeps the runtime import graph acyclic and preserves lazy/public XLSX boundaries already enforced by KAORI architecture checks.

### Preparation contract

Every preparer retains the current callable shape:

`(payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile) -> AnalyticsWorkbookData`

Preparation remains deterministic and side-effect free. It may normalize committed payload values and construct typed workbook data, but it must not query integrations, read persistence, calculate a new forecast, synthesize recommendations, or reinterpret missing evidence as a healthy state.

### Error handling

Unsupported report types continue to fail through the existing facade with a bounded `ValueError`. Context/report-type mismatch remains fail-fast. Extraction must not introduce broad exception handling, silent fallbacks, or source substitution. Report-family helpers may return neutral `Not Available`/empty evidence only where the current contract already does so.

### Regression and TDD requirements

Before each production extraction, a failing characterization/architecture contract must prove the intended new ownership boundary. GREEN evidence must cover both structural and behavioral contracts:

- facade symbols and report-type registry remain import-compatible;
- every enabled Analytics report type prepares successfully from its existing characterization payload;
- overview metrics, table names, columns, rows, readout text, chart type, chart source rows, series metadata, and units remain semantically equivalent;
- generated workbook sheet names, cells, formulas, number formats, chart XML/series, and runtime artifact validation remain covered by existing Analytics XLSX tests;
- Ruff/format, Pyright, architecture/import graph, code-health, exact debt baseline, taxonomy, and coverage remain green before a debt-ledger entry is lowered or removed.

### Code-health completion criteria

For this refactor increment:

- `analytics_profiles.py` must fall below the default 800-line module ceiling without replacing it with another oversized catch-all module;
- `_prepare_object_storage`, `_prepare_overview`, and `_prepare_top_consumers` must no longer require debt-ledger exceptions under the unchanged defaults of 160 function lines and 30 branch points;
- any newly extracted module/function must comply with default code-health ceilings on creation;
- the exact debt ledger may only decrease after the corresponding source structure is proven green;
- broad exception count must not increase.

This is a behavior-preserving code-health refactor. No report catalog, workbook schema, publication semantics, XLSX presentation standard, or external API change is part of Issue #13.
