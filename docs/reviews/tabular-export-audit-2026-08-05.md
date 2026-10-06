# KAORI CSV and XLSX Export Audit — 2026-08-05

## Decision

Analytics CSV and Inventory CSV/XLSX are standardized under `kaori-tabular-export-v2.0`. Inventory formats now share one dataset model; XLSX presentation is print-ready and CSV records are reconstructable and auditable.

## Findings remediated

1. CSV v1 repeated basic metadata but did not expose schema version, format standard, generated-by, classification, source, stable dataset names, field order, or value type.
2. Analytics table cells used generated `table:title` labels without a durable row reference.
3. Nested list/dict values used semicolon concatenation, which was ambiguous when values contained delimiters.
4. Inventory CSV resolved profiles and rows independently from XLSX.
5. Inventory profiles stored brittle freeze-cell strings even though identity columns already existed.
6. XLSX did not show selected-cluster context on the primary sheet.
7. XLSX print settings, repeated headers, document footer, and bounded dynamic row heights were missing.
8. The Field Dictionary did not expose the canonical field key or Excel number format.
9. Empty Inventory CSV lost report metadata because it emitted only a header.

## Result

- CSV standard: `kaori-reporting-csv-v2.0`
- XLSX standard: `kaori-inventory-xlsx-v2.0`
- Shared standard: `kaori-tabular-export-v2.0`
- Inventory sheets: exactly `Inventory`, `Metadata`, `Field Dictionary`
- Identity columns: one source for CSV references and XLSX freeze panes
- Missing values: shared profile rules
- TLS private material: excluded
- Formula injection: escaped
- Empty CSV: explicit `no_data` record

## Follow-up review

Generate one Analytics CSV and one Inventory CSV/XLSX from a production selected-cluster payload. Confirm that:

- the document reference matches the corresponding generated report;
- row counts match the committed source;
- Excel filter/freeze/print behavior is usable with long identities;
- downstream CSV consumers accept schema version 2.0;
- no private or raw Secret material is present.
