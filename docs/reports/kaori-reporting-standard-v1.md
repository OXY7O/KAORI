# KAORI Reporting Standard v1

**Status:** Default and mandatory
**Effective date:** 2026-08-03
**Scope:** Kubernetes and Object Storage Analytics/Inventory report generation

This document is the canonical implementation contract for KAORI report artifacts. A report type, output format, source boundary, metadata rule, and renderer must conform to this standard before it can be exposed in Generate Report, Templates, Schedules, Generated Reports, or worker execution.

## 1. Supported artifact matrix

| Report family | Default format | Additional format | Disallowed formats |
|---|---|---|---|
| Analytics (Kubernetes and Object Storage) | PDF | XLSX, CSV | — |
| Inventory (Kubernetes and Object Storage) | XLSX | CSV | PDF |

The authoritative matrix is defined in `app/reports/catalog.py`. UI code, routes, schedules, templates, artifact naming, and workers must consume that catalog. They must not maintain separate hard-coded format lists.

## 2. Mandatory selected-asset boundary

Every report requires exactly one canonical infrastructure asset scope.

- Kubernetes report types require one explicit selected Kubernetes cluster. Cross-cluster generation is prohibited.
- Object Storage report types require one explicit selected Object Storage system and do not require a Kubernetes `cluster_id`.
- The Generate Report, Templates, and Schedules surfaces must expose only scope types declared by the Definition Registry.
- Validation must reject an empty, unknown, or mismatched asset scope before a report record is created.
- Collectors must resolve exactly the asset stored on the report and must never select a first/default cluster, system, or provider binding.
- Kubernetes Inventory queries use the selected cluster and latest committed inventory generation.
- Kubernetes Analytics evidence uses the same selected-cluster boundary across materialized analytics, metrics, alerts, and supporting inventory.
- Object Storage Inventory and Analytics use the selected Object Storage system boundary across committed inventory, analytics snapshots, metrics evidence, and alerts.
- Storage naming must include the canonical asset scope and must reject an unscoped report.
- A schedule whose asset scope is missing or whose report contract is invalid must record a failed run and must not create an artifact.

Namespace is optional only for Kubernetes-scoped reports. An empty namespace means all namespaces **inside the selected cluster only**. Object Storage uses system scope and records namespace as `Not Applicable`.

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

Analytics PDF, XLSX, and CSV use the same canonical Analytics collector. PDF/CSV continue to derive publication structures from the canonical Analytics evidence model; XLSX adapts that same committed payload into its category-owned workbook profile without performing independent source queries.

Canonical sources include:

- selected-cluster Kubernetes Analytics materialized snapshots;
- selected-cluster Metrics Source and Alertmanager observation/cache data;
- selected-cluster committed Kubernetes inventory used as supporting evidence;
- selected-system Object Storage analytics/materialized evidence;
- selected-system Object Storage metrics and alert evidence when configured;
- selected-system committed Object Storage inventory used as supporting evidence;
- report and schedule activity filtered to the same canonical asset boundary.

A renderer must not perform an independent source query that would make PDF and CSV disagree. Source failures must be represented as an explicit failed generation or an explicit evidence limitation supported by the report-specific presentation contract.

### 4.2 Inventory

Inventory XLSX and Inventory CSV use the same collector, `InventoryExportContext`, row normalizer, profile, column order, and missing-value rules.

Canonical sources:

- Kubernetes Inventory: the latest committed Kubernetes inventory generation for the exact selected cluster, optionally filtered by namespace when supported;
- Object Storage Inventory: the latest committed Object Storage inventory generation for the exact selected system;
- TLS Inventory: committed certificate metadata and usage evidence inside the selected Kubernetes cluster/namespace boundary.

Artifact generation must not call the live Kubernetes API. Generated inventory is an auditable snapshot. Live operational actions must be verified separately against current cluster state.

TLS inventory exports certificate metadata and evidence only. Secret values, certificate private keys, and raw Secret payloads are prohibited in every format.

## 5. Shared metadata contract

Every artifact must preserve these logical fields where the format supports them:

- report standard/version;
- report ID and report name;
- report type and report family;
- selected infrastructure asset and asset type;
- namespace boundary where applicable;
- period or snapshot label;
- data cutoff/collection time;
- generated time and generated-by snapshot;
- source label and classification where applicable.

Labels, period names, cluster names, namespace semantics, and data cutoff must not vary between formats for the same report record.

## 6. PDF default style — Analytics

Analytics PDF is the only PDF family. Kubernetes and Object Storage Analytics share the same publication family and reference profile.

- Engine: WeasyPrint.
- Shared publication component: `app/templates/reports/pdf/components/analytics_publication.html`.
- Shared stylesheet: `app/static/reports/pdf/analytics_publication.css`.
- Report-specific templates and CSS may specialize content but must not redefine the shared header, title, footer, metric strip, section, table, cover, and semantic-status primitives.
- Palette follows KAORI Violet: primary `#7C3AED`, dark `#5B21B6`, soft `#EDE9FE`; semantic green, blue, amber, red, and slate are used only for status meaning.
- Tables are left-aligned, vertically centered, fixed-layout, readable, and must not truncate evidence with ellipsis.
- Section ordering comes from the canonical report catalog/template contract.
- The HTML template and WeasyPrint engine must not query external systems.

A PDF artifact is valid only when it exists, has a plausible size, and starts with the `%PDF-` signature.

## 7. XLSX default style — global KAORI workbook contract

Every XLSX report uses the global `kaori-reporting-xlsx-v2.0` contract. Inventory XLSX additionally uses
`kaori-inventory-xlsx-v4.0`; Analytics XLSX uses `kaori-analytics-xlsx-v1.0`. PDF remains the default Analytics publication, while XLSX is the governed analysis artifact for drill-down, filtering, trends, and inspectable evidence.

Inventory XLSX uses exactly four reusable sheets:

1. `Overview` — executive workbook landing page with domain-aware snapshot metrics, an evidence-derived Executive Readout, a profile-owned Primary Visual, exact Supporting Data, and internal navigation;
2. `Inventory` — report-specific public columns from the canonical inventory profile;
3. `Metadata` — grouped report identity, reporting boundary, workbook contract, data handling, and security evidence;
4. `Field Dictionary` — column definition, type, source, missing-value rule, semantic role, unit, and Excel format.

Default workbook rules:

- KAORI Violet title/header hierarchy with restrained use of semantic status colors;
- Office-native Aptos/Aptos Display fonts are used for workbook portability; this is the approved XLSX font-family exception to the Inter-based PDF publication style;
- `Overview` is always the first worksheet and acts as the primary reading and navigation surface;
- Overview metrics are domain-owned; schema counts such as column count or identity-field count are not executive KPIs;
- every XLSX report profile declares exactly four evidence-backed Overview metrics and exactly one primary chart contract;
- ranked numeric comparisons use `ranked_bar`: horizontal bars, descending Top-N order, one KAORI series color, zero baseline, direct value labels, no redundant legend, and a maximum of eight displayed categories;
- compact status/composition summaries use `doughnut`: a restrained semantic palette, bottom legend, percent-only labels, leader lines, and a dedicated visual gutter so labels never compete with Supporting Data;
- every chart is paired with a Supporting Data register containing rank, complete category text, exact value, and share so chart interpretation never depends on visual estimation;
- Executive Readout prose is derived only from committed workbook evidence and must not invent recommendations or health conclusions;
- Inventory, Metadata, and Field Dictionary include a visible `← Overview` link;
- typed numeric cells are right aligned; text cells are left aligned; structured tables retain filters and freeze panes;
- public capacity/usage values use readable units such as MiB/GiB/TiB rather than raw bytes when a readable unit is available;
- long identities remain complete in the workbook even when chart Top-N presentation is intentionally compact;
- empty datasets retain valid headers/table structure and show explicit no-evidence text instead of synthetic metrics or charts;
- private keys and Secret values are always excluded;
- the serialized artifact is validated after save and rejected when sheet order, navigation, executive sections, chart behavior, supporting data, or contract identifiers drift from the canonical standard.



Analytics XLSX uses a category-owned sheet contract. It always begins with `Overview` and ends with `Metadata` and `Field Dictionary`; evidence-bearing intermediate sheets are included only when committed evidence exists. Supported semantic sheet names include `Analysis`, `Trends`, `Breakdown`, `Top Consumers`, `Alerts & Anomalies`, and `Recommendations`. The renderer must not add empty decorative sheets.

Analytics workbook rules:

- exactly four domain-owned executive metrics are defined by the Analytics workbook profile;
- the Executive Readout is derived only from committed payload evidence and does not invent health conclusions;
- ordered time series use line charts with a bottom legend and inspectable source rows;
- ranked consumers use descending horizontal bars with direct value labels and Supporting Data;
- meaningful status composition uses compact doughnut charts with percentage-only labels and a bottom legend;
- capacity views use governed used/headroom percentage semantics when those values already exist in the canonical payload;
- forecasts and recommendations remain backend-owned; Excel presents committed values and never computes a forecast or creates a recommendation at export time;
- all category sheets provide a visible `← Overview` link, typed cells, bounded widths, native filters/tables, and spreadsheet formula-injection protection;
- post-save runtime validation rejects stale contract identifiers, broken navigation, or nonconforming chart semantics.

Inventory schema/profile definitions are in `app/reports/export/xlsx/standard.py`; Analytics schema/profile definitions are in `app/reports/export/xlsx/analytics_schema.py` and `app/reports/export/xlsx/analytics_profiles.py`. Shared Inventory collection/context/normalization logic is in `app/reports/export/inventory_common.py`. Analytics XLSX reuses the canonical Analytics collector used by the other Analytics formats. The cross-format contract is defined in [`kaori-tabular-export-standard-v3.md`](kaori-tabular-export-standard-v3.md).

## 8. CSV default style — Analytics and Inventory

CSV standard identifier: `kaori-reporting-csv-v3.0`. Interoperability profile: `portable-tabular-v1`. CSV is a machine-readable exchange artifact, not a visual report; it deliberately has no decorative presentation layer.

Common rules:

- encoding: UTF-8 with BOM (`utf-8-sig`);
- delimiter: comma;
- line ending: LF;
- quoting/escaping: Python `csv.DictWriter`;
- stable header order;
- ISO-8601 date/time values;
- compact deterministic JSON serialization for list/dict values;
- cells beginning with spreadsheet formula control characters are escaped;
- no decorative rows, merged cells, or format-specific presentation logic;
- public storage/capacity values use readable numeric units instead of primary raw-byte columns.

Analytics CSV is a normalized long-form export of the same `ReportDocument` used by PDF. It contains source metrics, section status, metrics, findings, table cells, notes, and methodology records. Simple numeric display values expose the numeric `value` separately from `unit` so the CSV stays sortable and easy to process.

Inventory CSV contains common report metadata, `record_type`, `record_reference`, `row_number`, and the same normalized report-specific columns and ordering used by the XLSX Inventory sheet. An empty inventory dataset produces one explicit `no_data` row so metadata and the selected-asset boundary remain auditable.

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

Object keys include domain, source kind, year/month, canonical asset-scope slug, report type, namespace/system marker, period, timestamp, and unique suffix. A generic artifact route is used for generation and download; format-specific legacy routes are prohibited.

## 10.1 Cross-format acceptance rules

The report portfolio is considered aligned only when all three artifact contracts agree on identity, source boundary, and semantics:

- **PDF:** management publication for Analytics only; concise comparison registers, references for long identities, shared Analytics Overview typography hierarchy, and no renderer-side source queries.
- **XLSX:** governed workbook artifact for both families. Inventory uses exactly `Overview`, `Inventory`, `Metadata`, and `Field Dictionary`; Analytics uses `Overview`, category-owned evidence sheets, `Metadata`, and `Field Dictionary`. Both families require domain metrics, evidence-derived readout, semantic visualization/supporting evidence, typed cells, navigation, formula safety, runtime artifact validation, and no private Secret material. Legacy `.xls` is not supported.
- **CSV:** machine-readable companion for both families; UTF-8 BOM, LF, stable schema/order, ISO-8601 temporal values, deterministic nested JSON, formula-injection protection, and the same canonical source model used by PDF/XLSX.
- The public document reference, report type, family, scope, period, data cut-off, generated-by snapshot, and source label must be semantically identical across formats for the same report definition/generation boundary.
- A report-specific renderer may change presentation only; it must not change the underlying evidence denominator, missing-value meaning, identity, or ordering semantics.

## 11. Prohibited implementation patterns

Do not introduce:

- a cross-cluster, cross-system, default-cluster, or default-system fallback;
- a global `pdf` or `xlsx` default applied to every family;
- format-specific duplicate collectors;
- PDF rendering for Inventory;
- independent CSV field maps that can drift from PDF/XLSX models;
- renderer-side external data queries;
- duplicated report type labels, descriptions, icons, sections, or format matrices;
- format-specific route aliases such as `generate_pdf` or `download_pdf`;
- compatibility aliases that preserve removed report types or payload field names;
- silent fallback for unsupported report types/formats;
- Secret values or TLS private-key material in exported artifacts.

## 12. Adding or changing a report

A change is complete only when it updates, as applicable:

1. `app/definitions/catalogs/reports/catalog.yaml` — type, family, default/allowed formats, sections, period mode, domain, and canonical scope asset;
2. one canonical collector/payload contract;
3. Analytics `ReportDocument`/Analytics XLSX profile presentation or Inventory profile;
4. renderer registry only when adding a new file format;
5. template/schedule UI derived data, not hard-coded options;
6. storage extension/MIME behavior through the format catalog;
7. unit/contract tests for format matrix, invalid-scope rejection, source reuse, schema/layout, public-reference coverage, and sensitive-data exclusion;
8. this standard when the default contract changes.

## 13. Quality gate

Before merge:

- Python compile checks pass;
- report tests pass;
- Jinja templates parse;
- the catalog matrix equals the artifact registry matrix;
- every report type has one registered collector/presentation path;
- no removed route, renderer, template, stylesheet, report type, or compatibility alias remains;
- generated PDF/XLSX/CSV opens successfully and matches the selected canonical asset scope;
- `git diff --check` is clean.

## Analytics PDF publication contract

All Analytics PDF artifacts must follow `docs/reports/kaori-analytics-pdf-publication-standard-v3.md`. The v3 contract owns typography, vertical rhythm, concise table plus reference-register behavior, chart label collision handling, source-unavailable publication, and the public report reference convention.
