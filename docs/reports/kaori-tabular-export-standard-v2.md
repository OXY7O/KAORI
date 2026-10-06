# KAORI Tabular Export Standard v2

**Status:** Canonical and mandatory
**Effective date:** 2026-08-05
**Scope:** Analytics CSV, Inventory CSV, and Inventory XLSX

This standard defines one reusable tabular-export contract for KAORI. CSV and XLSX are different serializations of shared report metadata, source boundary, field order, record identity, missing-value rules, and security controls. A renderer may add format-specific usability features, but it must not create a second data model.

## 1. Artifact matrix

| Family | CSV | XLSX |
|---|---|---|
| Kubernetes Analytics | Supported | Not supported |
| Kubernetes Inventory | Supported | Supported |

Analytics CSV is a normalized analytical dataset. Inventory CSV and XLSX are two serializations of the same `InventoryExportDataset`.

## 2. Standard identifiers

| Contract | Identifier |
|---|---|
| Shared tabular contract | `kaori-tabular-export-v2.0` |
| CSV format contract | `kaori-reporting-csv-v2.0` |
| Inventory workbook contract | `kaori-inventory-xlsx-v2.0` |
| Schema version | `2.0` |

The public document reference follows the KAORI report-reference convention. Internal database IDs are not document numbers.

## 3. Shared metadata

Every CSV row and the XLSX Metadata sheet preserve:

- format standard;
- shared tabular standard;
- schema version;
- document reference;
- report name;
- report type and user-facing label;
- report family;
- classification;
- generated timestamp and generated-by snapshot;
- selected cluster;
- namespace boundary;
- reporting period or snapshot label;
- data cut-off;
- canonical source label.

Metadata is produced by `TabularExportMetadata`. A format renderer must not rename, reinterpret, or independently calculate these values.

## 4. Shared Inventory dataset

Inventory XLSX and CSV use:

```text
collector
→ InventoryExportContext
→ InventoryWorkbookProfile
→ InventoryExportDataset
→ CSV or XLSX renderer
```

`InventoryExportDataset` owns:

- one report profile;
- one selected-cluster context;
- one ordered row collection;
- one identity-column contract;
- one row count;
- stable record-reference generation.

A renderer must not call a second collector, define a separate field map, reorder columns, or apply a different missing-value rule.

Identity columns must be the leading profile columns. They are used to build CSV `record_reference` values and to determine frozen columns in XLSX.

## 5. Analytics CSV v2

Analytics CSV uses one long-form record schema:

```text
shared metadata
section_order
section_key
section_title
dataset
record_type
record_reference
record_order
field_order
field
value
value_type
status
tone
note
```

### Record identity

- Source metric: `SRC-M01`
- Section: `S01`
- Section metric: `S01-M01`
- Finding: `S01-F01`
- Methodology note: `MET-N01`
- Table row: use the committed first-column reference when the first header is `Ref.`, `Reference`, `ID`, or `Code`; otherwise use `S01-T01-R0001`.

Each table field is a separate long-form row with the same `record_reference`. `field_order` reconstructs the original column order.

### Value rules

- date/time: ISO 8601;
- boolean: lowercase `true` or `false`;
- mapping/array: compact deterministic JSON;
- missing value: empty field;
- spreadsheet control characters (`=`, `+`, `-`, `@`) are escaped before writing.

The CSV renderer does not reproduce PDF layout or chart geometry. It preserves analytical evidence in a stable machine-readable form.

## 6. Inventory CSV v2

Inventory CSV contains:

```text
shared metadata
record_type
record_reference
row_number
report-specific Inventory columns
```

Data rows use `record_type=inventory_asset`. The record reference joins the canonical identity columns in profile order. If identity evidence is missing, the renderer uses a deterministic `REPORTTYPE-000001` fallback.

An empty dataset emits one explicit `no_data` record so report metadata and selected-cluster scope remain auditable. Asset columns remain empty.

CSV format rules:

- UTF-8 with BOM;
- comma delimiter;
- LF line ending;
- stable header order;
- Python CSV quoting;
- formula-injection protection;
- no decorative rows;
- no hidden truncation;
- no duplicate collector or field mapping.

## 7. Inventory XLSX v2

XLSX keeps exactly three sheets:

1. `Inventory`
2. `Metadata`
3. `Field Dictionary`

### Inventory sheet

Rows are standardized:

| Row | Purpose |
|---:|---|
| 1 | KAORI title |
| 2 | Report description |
| 3 | Reference, selected scope, cut-off, and row count |
| 4 | Whitespace separator |
| 5 | Column headers |
| 6+ | Inventory records |

Rules:

- one Excel table;
- stable profile column order;
- identity columns frozen automatically;
- header rows repeated for print;
- A4 landscape, fit-to-width printing;
- footer contains document reference and page number;
- wrapped values and bounded row-height estimation;
- numeric values remain numeric;
- numeric missing values remain blank;
- missing text uses the profile rule, normally `Not Available`;
- status columns use semantic conditional formatting;
- no formulas are generated from user-controlled values.

### Metadata sheet

The sheet records workbook, tabular, schema, source, scope, generation, security, row count, identity, and CSV-parity controls.

### Field Dictionary sheet

The dictionary contains:

- field key;
- display column;
- definition;
- data type;
- source/rule;
- missing-value rule;
- semantic role;
- Excel number format.

## 8. Typography and color

XLSX uses one shared style owner in `app/reports/export/xlsx/style.py`.

- title font: Aptos Display, 16 pt;
- body font: Aptos, 9 pt;
- header font: Aptos, 10 pt semibold;
- KAORI Dark Violet: `#5B21B6`;
- KAORI Bright Violet: `#7C3AED`;
- KAORI Soft Violet: `#EDE9FE`;
- semantic colors are used only for status meaning;
- data cells are left aligned, vertically centered, and wrapped.

A report profile owns data semantics and preferred widths. It does not own duplicate styles, row numbers, freeze-cell strings, or print configuration.

## 9. Security

- CSV formula injection is escaped.
- TLS private keys, Secret values, and recoverable key material are prohibited.
- XLSX contains values, not user-controlled formulas.
- Missing evidence is explicit and never converted to a healthy value.
- The renderer does not query Kubernetes, Prometheus, Alertmanager, S3, or another external provider.

## 10. DRY ownership

| Concern | Owner |
|---|---|
| Shared metadata and scalar serialization | `app/reports/export/tabular.py` |
| Inventory context, dataset, rows, identity | `app/reports/export/inventory_common.py` |
| Inventory fields and order | `app/reports/export/xlsx/standard.py` |
| CSV schema | `app/reports/export/csv/standard.py` |
| CSV serialization | `app/reports/export/csv/renderer.py` |
| XLSX style primitives | `app/reports/export/xlsx/style.py` |
| XLSX sheet composition | `app/reports/export/xlsx/builder.py` |

## 11. Prohibited patterns

Do not add:

- separate Inventory field maps for CSV and XLSX;
- hard-coded freeze cells in every profile;
- renderer-specific source queries;
- semicolon-based nested serialization;
- incremental database IDs as public references;
- header-only empty CSV that loses report metadata;
- formulas built from exported text;
- unbounded Excel column width or row height;
- hidden ellipsis or silent truncation;
- extra workbook sheets without updating this standard.

## 12. Quality gate

Run:

```bash
python scripts/verify_tabular_export_standard.py
pytest -q tests/reports/test_report_csv_standard.py tests/reports/test_inventory_xlsx_standard.py
```

The verifier checks standard identifiers, shared metadata, dataset reuse, identity ownership, CSV references, XLSX sheet layout, print behavior, formula protection, documentation, and quality-gate registration.
