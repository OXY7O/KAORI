# KAORI Reporting Standard v1

**Status:** Default and mandatory
**Effective date:** 2026-08-03
**Scope:** Kubernetes Analytics and Kubernetes Inventory report generation

This document is the canonical implementation contract for KAORI report artifacts. A report type, output format, source boundary, metadata rule, and renderer must conform to this standard before it can be exposed in Generate Report, Templates, Schedules, Generated Reports, or worker execution.

## 1. Supported artifact matrix

| Report family | Default format | Additional format | Disallowed formats |
|---|---|---|---|
| Kubernetes Analytics | PDF | CSV | XLSX |
| Kubernetes Inventory | XLSX | CSV | PDF |

The authoritative matrix is defined in `app/reports/catalog.py`. UI code, routes, schedules, templates, artifact naming, and workers must consume that catalog. They must not maintain separate hard-coded format lists.

## 2. Mandatory selected-cluster boundary

Every report requires one explicit `cluster_id`.

- Cross-cluster report generation is prohibited.
- The Generate Report and Schedule forms must not expose a cross-cluster option.
- Validation must reject an empty or unknown cluster before a report record is created.
- Collectors must resolve exactly the cluster stored on the report and must never choose a first/default cluster.
- Inventory queries must filter by the selected cluster and the latest committed inventory generation.
- Analytics queries, materialized snapshots, Prometheus/Alertmanager observations, report activity, and supporting inventory evidence must use the same selected-cluster boundary.
- Storage naming must include the selected cluster and must reject an unscoped report.
- A schedule whose cluster is missing or whose report contract is invalid must record a failed run and must not create an artifact.

Namespace is optional. An empty namespace means all namespaces **inside the selected cluster only**.

## 3. Canonical generation pipeline

All formats use the same high-level pipeline:

1. `app/reports/catalog.py` validates the report type, family, selected cluster, and allowed output format.
2. The family collector builds one canonical payload for the selected cluster.
3. A reusable document/export model normalizes metadata, rows, status, missing values, and field order.
4. `app/reports/export/artifacts.py` resolves the renderer from the output format registry.
5. The renderer writes a staging artifact and performs format-specific validity checks.
6. Storage persists the artifact using `app/reports/storage/naming.py`.
7. The report record is updated to `ready`; a failed regeneration retains an already-ready artifact.

Renderers must not silently substitute another format, report type, cluster, or source.

## 4. Source-of-truth rules

### 4.1 Analytics

Analytics PDF and Analytics CSV use the same collector and `ReportDocument` model.

Canonical sources include:

- selected-cluster Analytics materialized snapshots;
- selected-cluster Prometheus observation/cache data;
- selected-cluster Alertmanager observation/cache data;
- selected-cluster committed Kubernetes inventory used as supporting evidence;
- selected-cluster report and schedule activity for reporting-summary sections.

A renderer must not perform an independent source query that would make PDF and CSV disagree. Source failures must be represented as an explicit failed generation or an explicit evidence limitation supported by the report-specific presentation contract.

### 4.2 Inventory

Inventory XLSX and Inventory CSV use the same collector, `InventoryExportContext`, row normalizer, profile, column order, and missing-value rules.

Canonical source:

- the latest committed Kubernetes inventory generation;
- filtered by the exact selected cluster;
- optionally filtered by namespace when the report type supports namespace scope.

Artifact generation must not call the live Kubernetes API. Generated inventory is an auditable snapshot. Live operational actions must be verified separately against current cluster state.

TLS inventory exports certificate metadata and evidence only. Secret values, certificate private keys, and raw Secret payloads are prohibited in every format.

## 5. Shared metadata contract

Every artifact must preserve these logical fields where the format supports them:

- report standard/version;
- report ID and report name;
- report type and report family;
- selected cluster;
- namespace boundary;
- period or snapshot label;
- data cutoff/collection time;
- generated time and generated-by snapshot;
- source label and classification where applicable.

Labels, period names, cluster names, namespace semantics, and data cutoff must not vary between formats for the same report record.

## 6. PDF default style — Analytics

Analytics PDF is the only PDF family.

- Engine: WeasyPrint.
- Shared publication component: `app/templates/reports/pdf/components/analytics_publication.html`.
- Shared stylesheet: `app/static/reports/pdf/analytics_publication.css`.
- Report-specific templates and CSS may specialize content but must not redefine the shared header, title, footer, metric strip, section, table, cover, and semantic-status primitives.
- Palette follows KAORI Violet: primary `#7C3AED`, dark `#5B21B6`, soft `#EDE9FE`; semantic green, blue, amber, red, and slate are used only for status meaning.
- Tables are left-aligned, vertically centered, fixed-layout, readable, and must not truncate evidence with ellipsis.
- Section ordering comes from the canonical report catalog/template contract.
- The HTML template and WeasyPrint engine must not query external systems.

A PDF artifact is valid only when it exists, has a plausible size, and starts with the `%PDF-` signature.

## 7. XLSX default style — Inventory

Inventory XLSX uses `kaori-inventory-xlsx-v1.0` and exactly three reusable sheets:

1. `Inventory` — report-specific columns from the canonical inventory profile;
2. `Metadata` — scope, source, cutoff, ownership, format, security, and standard information;
3. `Field Dictionary` — column definition, type, source, and missing-value rule.

Default workbook rules:

- KAORI Violet title/header hierarchy;
- left horizontal alignment and middle vertical alignment;
- wrapped text, filter, freeze pane, and one Excel table on each structured sheet;
- stable report-specific column order;
- numeric missing values remain blank;
- text missing values use `Not Available` unless the profile defines another rule;
- empty datasets retain valid headers/table structure and show an explicit no-data message;
- private keys and Secret values are always excluded.

The reusable schema is defined in `app/reports/export/xlsx/standard.py`; shared collection/context/row logic is in `app/reports/export/inventory_common.py`.

## 8. CSV default style — Analytics and Inventory

CSV standard identifier: `KAORI Reporting CSV v1`.

Common rules:

- encoding: UTF-8 with BOM (`utf-8-sig`);
- delimiter: comma;
- line ending: LF;
- quoting/escaping: Python `csv.DictWriter`;
- stable header order;
- ISO-8601 date/time values;
- semicolon-separated serialization for list/dict values;
- cells beginning with spreadsheet formula control characters are escaped;
- no decorative rows, merged cells, or format-specific presentation logic.

Analytics CSV is a normalized long-form export of the same `ReportDocument` used by PDF. It contains source metrics, section status, metrics, findings, table cells, notes, and methodology records.

Inventory CSV contains common report metadata, `row_number`, and the same report-specific columns and ordering used by the XLSX Inventory sheet. An empty inventory dataset produces a header-only CSV, which is the canonical machine-readable no-data representation.

## 9. Template and schedule rules

- System templates are generated from `REPORT_TYPE_SPECS`; they are not manually duplicated constants.
- A template stores only a format allowed by its report type.
- Inventory sections are fixed to the reusable Inventory/Metadata/Field Dictionary contract.
- Analytics sections are restricted to the report type's catalog definition.
- A schedule stores and executes its selected output format; it must not force a family default after creation.
- Changing report type must reset only an incompatible output format or section selection.
- Generate, Template, and Schedule UI options must be derived from the same catalog payload.

## 10. Storage and download rules

Artifact extension and MIME type come from `OUTPUT_FORMAT_SPECS`:

- PDF: `.pdf`, `application/pdf`;
- XLSX: `.xlsx`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`;
- CSV: `.csv`, `text/csv`.

Object keys include domain, source kind, year/month, selected-cluster slug, report type, namespace, period, timestamp, and unique suffix. A generic artifact route is used for generation and download; format-specific legacy routes are prohibited.

## 11. Prohibited implementation patterns

Do not introduce:

- a cross-cluster/default-cluster fallback;
- a global `pdf` or `xlsx` default applied to every family;
- format-specific duplicate collectors;
- PDF rendering for Inventory or XLSX rendering for Analytics;
- independent CSV field maps that can drift from PDF/XLSX models;
- renderer-side external data queries;
- duplicated report type labels, descriptions, icons, sections, or format matrices;
- format-specific route aliases such as `generate_pdf` or `download_pdf`;
- compatibility aliases that preserve removed report types or payload field names;
- silent fallback for unsupported report types/formats;
- Secret values or TLS private-key material in exported artifacts.

## 12. Adding or changing a report

A change is complete only when it updates, as applicable:

1. `app/reports/catalog.py` — type, family, default/allowed formats, sections, period mode;
2. one canonical collector/payload contract;
3. Analytics `ReportDocument` presentation or Inventory profile;
4. renderer registry only when adding a new file format;
5. template/schedule UI derived data, not hard-coded options;
6. storage extension/MIME behavior through the format catalog;
7. unit/contract tests for format matrix, selected-cluster rejection, source reuse, schema/layout, and sensitive-data exclusion;
8. this standard when the default contract changes.

## 13. Quality gate

Before merge:

- Python compile checks pass;
- report tests pass;
- Jinja templates parse;
- the catalog matrix equals the artifact registry matrix;
- every report type has one registered collector/presentation path;
- no removed route, renderer, template, stylesheet, report type, or compatibility alias remains;
- generated PDF/XLSX/CSV opens successfully and matches the selected cluster;
- `git diff --check` is clean.

## 14. Storage connectivity and graceful degradation

Report storage is an external dependency and must never become a page-level availability dependency.

Mandatory behavior when the configured Local or S3-compatible backend cannot be reached:

- Reports Overview, Generate, Generated Reports, Report Detail, Schedules, and Reports Storage remain renderable from database metadata.
- The UI shows one sanitized storage state: `Connected`, `Disconnected`, or `Needs Review`; raw SDK exceptions, endpoint details, access keys, stack traces, and provider error payloads are never rendered.
- Existing report records, filters, pagination, templates, schedules, archive metadata, and non-storage navigation remain usable.
- Generation stops before PDF/XLSX/CSV rendering when the active backend is not writable, preventing wasted CPU and temporary files.
- Download and restore actions are paused only for artifacts whose backend cannot be reached. Mixed Local/S3 history remains backend-aware.
- Artifact probes are centralized in `app/reports/storage/service.py` and cached; templates and feature services must not instantiate S3 clients directly.
- Integrity and cleanup checks must report a sanitized backend-unavailable state rather than failing the whole page.
- S3/MinIO clients use bounded connect/read timeouts and retry attempts so disconnection is detected quickly.
- The Storage page provides a clear `Retry Connection` action and explains that report registry metadata remains protected.

Default resilience configuration:

- `REPORT_S3_CONNECT_TIMEOUT_SECONDS=2`
- `REPORT_S3_READ_TIMEOUT_SECONDS=3`
- `REPORT_S3_MAX_ATTEMPTS=1`
- `REPORT_STORAGE_STATUS_CACHE_SECONDS=15`

Any new report page or worker path that reads or writes artifacts must use `get_report_storage_backend_status()` and `probe_report_artifact()` instead of calling storage SDK methods from presentation code.
