# KAORI Tabular Export Standard v3

Status: Canonical

This standard defines the reusable CSV and XLSX publication contract for KAORI report artifacts. Report collectors own evidence; tabular renderers own presentation. New report types that enable CSV or XLSX must reuse this contract rather than creating format-specific schemas.

## 1. Contract identifiers

| Contract | Identifier |
| --- | --- |
| Shared tabular contract | `kaori-tabular-export-v3.0` |
| Public schema version | `3.0` |
| CSV format contract | `kaori-reporting-csv-v3.0` |
| Global XLSX format contract | `kaori-reporting-xlsx-v1.0` |
| Inventory workbook contract | `kaori-inventory-xlsx-v3.0` |

The catalog remains the authority for whether a report type supports PDF, CSV, or XLSX. This standard does not enable a new output format by itself.

## 2. Shared evidence rules

CSV and XLSX generated from the same Inventory report must use the same `InventoryWorkbookProfile`, normalized row set, identity columns, field order, data cut-off, and public reference semantics.

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

Every XLSX report published by KAORI must use the global `kaori-reporting-xlsx-v1.0` presentation contract. Inventory XLSX currently uses exactly these reusable sheets, in this order:

1. `Overview`
2. `Inventory`
3. `Metadata`
4. `Field Dictionary`

### Overview

The Overview sheet is the workbook landing page: management- and operator-readable while remaining derived from the same committed dataset. It includes:

- report title and stable report reference;
- explicit Key Metrics and General Information sections;
- selected infrastructure scope and namespace boundary;
- record count, public column count, identity-field count, and data cut-off;
- internal hyperlinks to every other workbook sheet;
- an explicit Visual Summary area with at least one evidence-backed visual summary when committed rows are available.

Charts are evidence-driven, not decorative. Every XLSX report profile must explicitly declare its chart title, category field, aggregation mode, and maximum displayed rows. Count charts aggregate committed records by a public categorical field; value charts use a committed numeric public field. Empty datasets show an explicit no-evidence message rather than inventing chart values.

### Inventory

The Inventory sheet is the canonical row-level dataset.

- identity columns lead the table and determine freeze-pane placement;
- headers have stable profile order;
- filters and a native Excel table are enabled;
- cells are left aligned, vertically centered, and wrapped;
- numeric/date values use typed Excel cells and explicit number formats;
- missing numeric values stay blank;
- missing text uses the profile missing-value rule, normally `Not Available`;
- column widths are profile-owned and bounded for readability;
- semantic status fields use conditional formatting owned by the shared builder.

### Metadata

Metadata records the workbook/tabular standards, report reference, report type/family, selected scope, namespace boundary, period, data cut-off, source, row count, identity columns, generation ownership, classification, parity rules, and security exclusions.

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

## 5. Human-readable units

Byte counts are valid internal source evidence but are not an acceptable primary public presentation when a readable capacity unit is available.

- bytes under 1 MiB may remain bytes only when byte-level precision is operationally meaningful;
- capacity/usage inventory should normally use MiB, GiB, or TiB;
- the published unit is explicit in the field label or the Field Dictionary;
- conversions occur before CSV/XLSX rendering so both formats have parity.

Object Storage Inventory publishes `Usage GiB`, `Quota GiB`, and `Quota Utilization %` rather than `Usage Bytes` and `Quota Bytes`.

## 6. Readability and chart policy

XLSX is an operational workbook, not a PDF imitation.

- Use native Excel tables, filters, freeze panes, typed cells, and native charts.
- Do not use screenshots of charts.
- Do not merge data-table cells.
- Overview charts are mandatory for every XLSX report profile and remain profile-owned.
- A chart must use committed public fields with a valid denominator/aggregation.
- Dense technical detail belongs in Inventory and Field Dictionary rather than oversized Overview prose.

## 7. Extension rule for future reports

A new CSV/XLSX-capable report must:

1. register format support in the canonical report catalog;
2. define or reuse a tabular profile with stable identities and field order;
3. define public units and missing-value behavior;
4. use shared normalization before rendering;
5. use the canonical CSV writer or XLSX builder;
6. declare a mandatory Overview chart using committed public fields;
7. add contract tests for schema order, unit transformations, empty data, security exclusions, and chart behavior.

Report-specific renderers must not fork the shared CSV encoding/safety contract or the XLSX Overview/Inventory/Metadata/Field Dictionary structure.
