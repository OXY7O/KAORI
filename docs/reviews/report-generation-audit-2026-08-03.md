# KAORI Report Generation Audit — 2026-08-03

## Objective

Audit and standardize report generation so that:

- Analytics produces PDF or CSV;
- Inventory produces XLSX or CSV;
- every report is scoped to one selected cluster;
- source collection, presentation contracts, storage naming, templates, schedules, and UI are reusable and consistent;
- obsolete PDF Inventory/TLS paths and format-specific aliases are removed.

## Principal findings

1. Output formats were globally modeled as PDF/XLSX and CSV had no artifact contract.
2. Inventory still had PDF collectors/templates/styles even though Inventory should be tabular XLSX/CSV.
3. Some analytics and inventory paths allowed an empty cluster or used services capable of selecting the first cluster as a fallback.
4. Report type labels, descriptions, readiness sets, formats, and system templates were duplicated across services.
5. Schedule and template flows could force a primary format instead of preserving a valid selected format.
6. Generic artifact actions still exposed PDF-named compatibility fields/routes.
7. Inventory CSV would have needed to duplicate workbook columns and normalization without a shared export contract.
8. Reporting-standard documentation described only PDF visual primitives and did not govern sources, formats, cluster scope, CSV, XLSX, scheduling, or storage.

## Remediation implemented

### Canonical catalog and validation

- Added `app/reports/catalog.py` as the single source of truth for report types and file formats.
- Defined Analytics as PDF/CSV and Inventory as XLSX/CSV.
- Added contract validation for report type, output format, and selected cluster.
- Replaced duplicated label/readiness/template catalogs with catalog-derived structures.

### Selected-cluster enforcement

- Generate and Schedule forms require a cluster and validate that it exists.
- Added `app/reports/export/payloads/common.py` to resolve the exact report cluster without fallback.
- Analytics and Inventory collectors enforce the selected cluster.
- Analytics reporting-summary and inventory-support sections are filtered to the same cluster.
- Schedule execution rejects invalid historical/unscoped contracts before creating a report.
- Storage naming rejects unscoped reports and includes the selected cluster in the object key.

### Reusable source and export contracts

- Analytics PDF and CSV share the same analytics collector and `ReportDocument` normalization.
- Inventory XLSX and CSV share `InventoryExportContext`, payload collection, row normalization, workbook profile, column order, and missing-value rules.
- Added canonical CSV renderer/standard with UTF-8 BOM, stable headers, ISO dates, and formula-injection protection.
- Added exact renderer guards so PDF, XLSX, and CSV renderers cannot be called with a different format contract.

### Legacy and waste removal

Removed:

- Inventory and TLS PDF renderers/builders;
- Inventory/TLS PDF templates and stylesheets;
- obsolete topology and certificate-health report paths;
- PDF-specific generate/download routes;
- PDF-named payload aliases in Generated Reports;
- duplicated report labels/descriptions and hard-coded implemented-report sets;
- unused Inventory/TLS PDF section branches.

### Template, schedule, and UI consistency

- System templates are generated directly from the report catalog.
- Templates store only formats allowed by their report family.
- Schedule creation/editing preserves valid PDF/CSV/XLSX choices.
- Generate, Templates, and Schedules expose the same format matrix and selected-cluster rule.
- Renderer-readiness wording now covers PDF, XLSX, and CSV.

### Documentation

- Replaced the old PDF-only note with `docs/reports/kaori-reporting-standard-v1.md`, which is now the default report-generation standard.

## Expected contract after remediation

| Family | Formats | Scope | Primary source/model |
|---|---|---|---|
| Analytics | PDF, CSV | One selected cluster | Shared analytics collector + `ReportDocument` |
| Inventory | XLSX, CSV | One selected cluster | Shared committed-inventory collector + inventory profile |

## Review checkpoints

- Unsupported family/format combinations fail explicitly.
- Missing cluster fails before collection/rendering.
- No collector can silently select another cluster.
- PDF is Analytics-only; XLSX is Inventory-only; CSV dispatches by family.
- CSV uses shared document/profile models rather than maintaining a parallel field map.
- Storage extension and MIME type come from the central format catalog.
- Secret values and TLS private keys remain excluded.

## Validation completed

- `python scripts/verify_python_syntax.py` — passed across 797 Python source files.
- `python scripts/verify_single_pdf_engine.py` — passed; PDF resolves only to the canonical WeasyPrint renderer.
- `python scripts/verify_report_generation_contract.py` — passed; catalog, format matrix, selected-cluster requirement, collector/profile coverage, registry, documentation, and removed legacy tokens are consistent.
- Reports Jinja parse — passed across 30 templates.
- Report contract/publication static tests — 19 passed.
- `git diff --check` — passed.

The Flask-dependent report tests could not be collected in the audit sandbox because the provided environment does not contain Flask and its package index does not expose the project-pinned Flask/aiohttp builds. Those tests remain in the repository and must run in the normal KAORI development container or CI environment before merge.

The repository-wide code-health gate still reports pre-existing complexity debt, including large Analytics PDF presentation modules. This remediation reduces report code volume and removes dead report paths, but does not claim to redesign every existing Analytics presentation function. The new report-contract gate prevents the removed format/scope/legacy behavior from returning while that separate complexity backlog is addressed.

## Follow-up portfolio audit — 2026-08-22

The report portfolio was re-audited after Analytics Overview v3 became the canonical PDF reference and Object Storage reporting was published.

### Portfolio coverage

- 20 published report types are present in the Definition Registry.
- 9 Analytics report types use PDF + CSV: 8 Kubernetes Analytics contracts and 1 Object Storage Analysis contract.
- 11 Inventory report types use XLSX + CSV: 10 Kubernetes/TLS inventory contracts and 1 Object Storage Inventory contract.
- Analytics PDF templates are registered in one WeasyPrint publication family and use the Analytics Overview typography/layout reference.
- Inventory XLSX and Inventory CSV reuse the same workbook profiles, identity-first column order, source dataset, and missing-value rules.
- Analytics PDF and Analytics CSV reuse the same collector and `ReportDocument` presentation/evidence model.

### Cross-format findings

1. The global reporting standard still described every report as Kubernetes-cluster-scoped even though Object Storage reports correctly use `object_storage_system` scope. Documentation was updated to one canonical infrastructure-asset boundary.
2. `object_storage_inventory` had no dedicated public report type code and therefore fell back to the generic `RPT` reference suffix. It now owns the canonical `OSI` code.
3. Several report-specific Analytics stylesheets still hard-coded methodology-table font sizes after Analytics Overview became the typography owner. Those overrides now reference the shared dense-table token instead of defining local typography.
4. XLSX intentionally uses Office-native Aptos/Aptos Display for client portability while preserving KAORI hierarchy, color, alignment, field order, metadata, dictionary, and conditional-status semantics. This is now documented as the workbook font-family exception rather than visual drift.
5. CSV is explicitly classified as a machine-readable exchange artifact. It must preserve data semantics and schema parity, not PDF/XLSX decorative styling.
6. Legacy `.xls` output is not supported; Inventory workbook output is `.xlsx` only.

### Portfolio acceptance result

The canonical artifact matrix remains:

| Family | Formats | Publication/data owner |
|---|---|---|
| Analytics | PDF, CSV | Shared collector + `ReportDocument`; Analytics Overview v3 is the PDF visual reference |
| Inventory | XLSX, CSV | Shared InventoryExportDataset + InventoryWorkbookProfile |

A report is release-ready only when the Definition Registry, renderer/profile coverage, public report reference, source/scope semantics, metadata fields, and family-specific style contract all agree.
