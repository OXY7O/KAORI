# KAORI Analytics XLSX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add governed Analytics XLSX artifacts for every published KAORI Analytics report type, with category-owned workbook layouts and consistent support information across Reports pages.

**Architecture:** Keep `kaori-reporting-xlsx-v2.0` as the global Excel presentation contract and introduce `kaori-analytics-xlsx-v1.0` as a separate analytics workbook family. Reuse canonical Analytics payload collectors already used by PDF/CSV, adapt those committed payloads into typed workbook presentation data, and route XLSX by report family through one format renderer. Catalog definitions remain the source of truth for UI, Templates, Schedules, and validation.

**Tech Stack:** Python, openpyxl, Flask/Jinja report catalog, pytest/static contract tests.

**Spec:** `docs/superpowers/specs/2026-08-26-kaori-analytics-xlsx-design.md`

## Global Constraints

- Global XLSX contract remains `kaori-reporting-xlsx-v2.0`.
- Analytics workbook contract is `kaori-analytics-xlsx-v1.0`.
- PDF remains the default Analytics publication format.
- Every published Analytics report type supports PDF, XLSX, and CSV.
- XLSX must consume the same committed canonical Analytics payload as PDF/CSV and must not calculate forecasts or recommendations itself.
- Every workbook starts with `Overview` and ends with `Metadata` and `Field Dictionary`.
- Category-specific evidence sheets are present only for semantic surfaces owned by that report category.
- KAORI Violet/Aptos, typed cells, formula-injection protection, bounded widths, internal navigation, and post-save validation are mandatory.

---

### Task 1: Lock Catalog and UI Format Contract

**Files:**
- Modify: `app/definitions/catalogs/reports/catalog.yaml`
- Modify: `app/reports/README.md`
- Modify: `app/reports/overview/presentation.py`
- Modify: `app/reports/overview/service.py`
- Modify: `app/templates/reports/overview/partials/_reporting_estate_capability.html`
- Modify: `app/templates/reports/overview/partials/_reporting_coverage.html`
- Modify: `app/templates/reports/overview/partials/_coverage_pipeline_workspace.html`
- Modify: `app/reports/report_templates/service.py`
- Test: `tests/reports/test_report_catalog.py`
- Test: `tests/contracts/reports/test_analytics_xlsx_reporting_surface_contract.py`

**Interfaces:**
- Consumes: canonical report catalog definitions.
- Produces: Analytics `allowed_formats = (pdf, xlsx, csv)` with PDF default; UI copy derives or states that three-format capability consistently.

- [ ] Write failing tests asserting every Analytics report supports PDF/XLSX/CSV and pages no longer state PDF/CSV-only.
- [ ] Run targeted tests and verify the failure is caused by missing Analytics XLSX support.
- [ ] Add `xlsx` to every Analytics report definition without changing `default_format: pdf`.
- [ ] Update Reports Overview, Generate-adjacent explanatory copy, Templates descriptions, and README to describe Analytics PDF/XLSX/CSV accurately.
- [ ] Run targeted tests to green.

### Task 2: Add Analytics XLSX Schema and Profiles

**Files:**
- Create: `app/reports/export/xlsx/analytics_schema.py`
- Create: `app/reports/export/xlsx/analytics_profiles.py`
- Modify: `app/reports/export/xlsx/__init__.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Produces: `ANALYTICS_WORKBOOK_STANDARD`, `ANALYTICS_XLSX_REPORT_TYPES`, `AnalyticsWorkbookProfile`, `AnalyticsWorkbookData`, and `prepare_analytics_workbook_data(report_type, payload, context)`.
- Profile adapters must exist for: `analytics_overview`, `resource_utilization`, `capacity_analysis`, `storage_analysis`, `workload_analysis`, `resource_forecast`, `top_consumers`, `alerts_anomalies`, `object_storage_analysis`.

- [ ] Write failing profile-contract tests for nine published Analytics report types, four overview metrics, category sheet declarations, and valid chart semantics.
- [ ] Run tests to verify RED.
- [ ] Implement typed Analytics presentation schema and profile registry.
- [ ] Implement evidence-preserving adapters with safe fallbacks and no invented recommendations/forecasts.
- [ ] Run tests to green.

### Task 3: Build Analytics Workbook Presentation Layer

**Files:**
- Create: `app/reports/export/xlsx/analytics_builder.py`
- Create: `app/reports/export/xlsx/analytics_overview.py`
- Reuse: `app/reports/export/xlsx/style.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Consumes: `AnalyticsWorkbookData`.
- Produces: XLSX with `Overview`, category-owned evidence sheets, `Raw Data` where applicable, `Metadata`, and `Field Dictionary`.
- Produces line, ranked-bar, and doughnut charts only from committed values present in workbook tables.

- [ ] Write failing workbook behavior tests for sheet ordering, Overview KPI/readout/navigation, chart type, source-data transparency, back navigation, metadata standards, and formula protection.
- [ ] Run tests to verify RED.
- [ ] Implement executive Overview and chart renderers.
- [ ] Implement generic evidence-table sheets, grouped Metadata, Field Dictionary, navigation, print/zoom/freeze settings, and native Excel tables.
- [ ] Implement runtime artifact validation for workbook family/version, canonical sheet boundaries, Overview navigation, and chart/source-data presence.
- [ ] Run tests to green.

### Task 4: Route Analytics XLSX Through Canonical Artifact Generation

**Files:**
- Modify: `app/reports/export/xlsx/renderer.py`
- Modify: `app/reports/export/artifacts.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`
- Test: `tests/contracts/reports/test_reports_platform_worker_delivery_redesign_contract.py`

**Interfaces:**
- Produces: `render_report_xlsx(report, output_path)` family dispatcher.
- Inventory continues through `render_inventory_xlsx`; Analytics uses canonical `collect_report_payload` then Analytics builder.

- [ ] Write failing renderer/registry contract tests.
- [ ] Run tests to verify RED.
- [ ] Add family-aware XLSX dispatcher and preserve Inventory compatibility entry point.
- [ ] Point artifact registry XLSX format at the family dispatcher.
- [ ] Run targeted tests to green.

### Task 5: Update Verification and Reporting Documentation

**Files:**
- Modify: `docs/reports/kaori-reporting-standard-v1.md`
- Modify: `docs/reports/kaori-tabular-export-standard-v3.md`
- Modify: `scripts/verify_report_generation_contract.py`
- Modify: `scripts/verify_tabular_export_standard.py`
- Test: `tests/contracts/reports/test_analytics_xlsx_reporting_surface_contract.py`

**Interfaces:**
- Produces: release guardrails that reject catalog/UI/renderer drift and document Analytics workbook category ownership.

- [ ] Write failing static verifier assertions.
- [ ] Run verifier/contracts to verify RED.
- [ ] Update standards and verifier scripts.
- [ ] Run verifier/contracts to green.

### Task 6: Regression, Preview, and Patch Packaging

**Files:**
- Test: all files above.
- Generate: representative Analytics XLSX previews for at least Resource Utilization, Forecast, Top Consumers, Alerts & Anomalies, and Object Storage Analysis.

**Interfaces:**
- Produces: final changed-files-only ZIP and deployment commands.

- [ ] Run Analytics XLSX tests, Inventory XLSX regression tests, catalog tests, static report contracts, and report verifier scripts.
- [ ] Open representative generated workbooks programmatically and confirm charts, sheet names, metadata, hyperlinks, and tables.
- [ ] Run Python syntax checks; run Ruff/full release gates when dependencies are available and report environmental blockers separately.
- [ ] Package only changed files and verify ZIP integrity/SHA-256.
