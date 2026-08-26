# KAORI Tabular Export Standard v3

Status: Canonical

This standard defines the reusable CSV and XLSX publication contract for KAORI report artifacts. Report collectors own evidence; tabular renderers own presentation. New report types that enable CSV or XLSX must reuse this contract rather than creating format-specific schemas.

## 1. Contract identifiers

| Contract | Identifier |
| --- | --- |
| Shared tabular contract | `kaori-tabular-export-v3.0` |
| Public schema version | `3.0` |
| CSV format contract | `kaori-reporting-csv-v3.0` |
| Global XLSX format contract | `kaori-reporting-xlsx-v2.0` |
| Inventory workbook contract | `kaori-inventory-xlsx-v4.0` |
| Analytics workbook contract | `kaori-analytics-xlsx-v1.0` |

The catalog remains the authority for whether a report type supports PDF, CSV, or XLSX. This standard does not enable a new output format by itself.

## 2. Shared evidence rules

Inventory CSV/XLSX generated from the same report must use the same `InventoryWorkbookProfile`, normalized row set, identity columns, field order, data cut-off, and public reference semantics. Analytics PDF/XLSX/CSV must reuse the same canonical Analytics collector and selected-asset evidence boundary; the XLSX adapter may reshape presentation but must not query a second source or change denominators.

- Internal database primary keys are not public report identities.
- Missing evidence remains explicit and is never translated into zero, healthy, or current state.
- Numeric values remain numeric whenever the format supports typed cells.
- Long technical identities remain complete; display formatting must not truncate committed evidence.
- Public storage values use readable binary units such as MiB, GiB, or TiB instead of exposing raw byte counts as primary columns.
- A profile may use a source field such as `size_bytes` while publishing a transformed field such as `usage_gib`; the transformation belongs to the reusable tabular profile, not to an XLSX-only renderer.

## 3. CSV standard

CSV is machine-first. It must remain straightforward to ingest with Python, spreadsheets, databases, and ETL pipelines.

The interoperability profile is `portable-tabular-v1`. KAORI CSV artifacts must round-trip through standard CSV parsers without custom preprocessing. Every CSV row carries the `interchange_profile` metadata field so consuming applications can identify the portability contract without relying on filenames.

Canonical rules:

- UTF-8 with BOM (`utf-8-sig`);
- comma delimiter;
- LF line termination;
- stable header order;
- ISO-8601 date/time values;
- deterministic compact JSON for nested values;
- formula-injection protection for spreadsheet control prefixes;
- deterministic `record_reference` values;
- no decorative rows, merged-cell concepts, prose-only headings, or visual chart data embedded as presentation markup.

### Analytics CSV

Analytics CSV is normalized long-form evidence derived from the same `ReportDocument` used by the Analytics PDF publication. The public fields include `value` and a separate `unit` field. Simple values such as `17.48 GiB`, `56.2%`, and `0.14 cores` are emitted as typed numeric `value` plus `unit`, preserving downstream sort/filter/aggregation behavior.

### Inventory CSV

Inventory CSV contains common metadata, `record_type`, `record_reference`, `row_number`, and the public columns from the same Inventory profile used by XLSX. Storage profiles publish readable numeric columns such as `usage_gib` and `quota_gib`; raw byte source fields remain implementation evidence and are not the primary exported columns.

## 4. XLSX standard

Every XLSX report published by KAORI must use the global `kaori-reporting-xlsx-v2.0` presentation contract. Inventory XLSX uses `kaori-inventory-xlsx-v4.0`; Analytics XLSX uses `kaori-analytics-xlsx-v1.0`.

Inventory XLSX uses exactly these reusable sheets, in this order:

1. `Overview`
2. `Inventory`
3. `Metadata`
4. `Field Dictionary`

### Overview

The Overview sheet is an executive landing page for management and operators while remaining strictly derived from the committed dataset. The canonical information hierarchy is:

1. report title, concise purpose, selected scope, period, and data cut-off;
2. `Executive Snapshot` with exactly four profile-owned operational metrics;
3. `Executive Readout` with one concise evidence-derived interpretation;
4. `Primary Visual` using the profile's semantic chart contract;
5. `Supporting Data` containing complete category names, exact values, ranking, and share;
6. `Workbook Navigation` with internal hyperlinks to the other sheets.

Schema diagnostics such as column count or identity-field count belong in Metadata and are not executive KPIs. Every XLSX report profile must declare its own metrics, record label, visual type, chart title, category field, aggregation mode, and Top-N boundary.

The supported visual semantics are explicit:

- `ranked_bar` — horizontal bar chart for ranked numeric values or high-cardinality comparisons. Values are sorted descending and limited to the declared Top-N, with a maximum of eight. The chart uses one KAORI violet series, `varyColors=False`, a zero baseline, direct value labels including the published unit where applicable, restrained/no major gridlines, and no redundant single-series legend.
- `doughnut` — compact part-to-whole/status composition for two to six displayed categories. It uses semantic category colors where status meaning exists, a bottom legend, percent-only data labels, explicit suppression of series/category/value label noise, leader lines, and a spacer between the visual and Supporting Data. When committed evidence contains more categories than the declared display limit, the remainder is aggregated into `Other` so the part-to-whole denominator remains complete.

Charts are evidence-driven, not decorative. Empty or non-chartable datasets show explicit no-evidence text instead of synthetic values. The Supporting Data register is mandatory whenever a chart is present so the workbook remains precise even when Excel renders chart labels differently across clients.

### Inventory

The Inventory sheet is the canonical row-level dataset.

- identity columns lead the table and determine freeze-pane placement;
- headers have stable profile order;
- filters and a native Excel table are enabled;
- numeric cells are right aligned while text cells are left aligned, with vertical centering and controlled wrapping;
- numeric/date values use typed Excel cells and explicit number formats;
- missing numeric values stay blank;
- missing text uses the profile missing-value rule, normally `Not Available`;
- column widths are profile-owned and bounded for readability;
- semantic status fields use conditional formatting owned by the shared builder;
- a visible `← Overview` link returns the reader to the landing page.

### Metadata

Metadata is a grouped reference surface rather than a flat undifferentiated list. It groups Report Identity, Reporting Boundary, Workbook Contract, Data Handling, and Security while retaining the same auditable values and public contract identifiers. It includes a `← Overview` link.

### Field Dictionary

The dictionary documents every public Inventory column with:

- field key;
- display label;
- definition;
- data type;
- source/rule;
- missing-value rule;
- semantic role;
- unit;
- Excel number format.

The technical table remains filterable and readable, with controlled wrapping and a `← Overview` link.

## 5. Human-readable units

Byte counts are valid internal source evidence but are not an acceptable primary public presentation when a readable capacity unit is available.

- bytes under 1 MiB may remain bytes only when byte-level precision is operationally meaningful;
- capacity/usage inventory should normally use MiB, GiB, or TiB;
- the published unit is explicit in the field label or the Field Dictionary;
- conversions occur before CSV/XLSX rendering so both formats have parity.

Object Storage Inventory publishes `Usage GiB`, `Quota GiB`, and `Quota Utilization %` rather than `Usage Bytes` and `Quota Bytes`.

## 6. Readability and chart policy

XLSX is an operational workbook, not a PDF imitation and not a raw data dump.

- Use native Excel tables, filters, freeze panes, typed cells, and native charts.
- Do not use screenshots of charts.
- Do not merge cells inside structured data tables.
- Use visual hierarchy and whitespace to separate executive summary, primary evidence, and technical reference material.
- Every XLSX report profile owns domain-aware Executive Snapshot metrics and a semantic Primary Visual contract appropriate to its family/category.
- Ranked bar charts must use descending order, one series color, direct value labels, and Supporting Data rather than rainbow bars or a redundant legend.
- Doughnut charts must be reserved for a small composition/status set where part-to-whole meaning is real; labels show percentage only, the legend sits below the chart, and the Supporting Data table remains visually separated from the chart.
- Complete long technical identities remain available in Supporting Data and Inventory even when the visual intentionally shows a Top-N subset.
- Dense technical detail belongs in Inventory and Field Dictionary rather than oversized Overview prose.
- Runtime validation must reject stale standard identifiers, missing executive sections, broken navigation, nonconforming ranked-bar coloring, or missing Supporting Data for chartable workbooks.

## 7. Extension rule for future reports

A new CSV/XLSX-capable report must:

1. register format support in the canonical report catalog;
2. define or reuse a tabular profile with stable identities and field order;
3. define public units and missing-value behavior;
4. use shared normalization before rendering;
5. use the canonical CSV writer or XLSX builder;
6. declare exactly four domain-aware Overview metrics plus a semantic chart contract using committed public fields;
7. add contract tests for schema order, metric semantics, unit transformations, empty data, security exclusions, navigation, supporting data, and chart behavior;
8. for Analytics, prove the XLSX adapter consumes the canonical Analytics payload and never creates forecasts or recommendations during export.

Report-specific renderers must not fork the shared CSV encoding/safety contract or their family-owned XLSX structure. Inventory retains the four-sheet Inventory contract; Analytics retains Overview + evidence-driven category sheets + Metadata + Field Dictionary.

### Analytics Overview evidence completeness

- Analytics Overview CSV keeps the canonical long-form `portable-tabular-v1` layout.
- Publication sections marked `Included` must resolve to structured committed evidence; sections without structured evidence are published as `No Evidence` or `Unavailable`, never as an `Included` section followed only by an empty-evidence note.
- `resource_posture` binds to the committed resource snapshot and `trend_forecast` binds to the committed forecast snapshot. Resource-level forecast records retain resource identity, latest/projected percentages, trend, and confidence rather than being reinterpreted as time-series observations.
- Analytics Overview XLSX presents resource-level forecast evidence as `Current vs Projected Resource Posture`; true line charts are reserved for ordered time-series datasets.
