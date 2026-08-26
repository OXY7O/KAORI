from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_v3_identifiers_and_unit_aware_analytics_csv_are_locked() -> None:
    tabular = read('app/reports/export/tabular.py')
    csv_standard = read('app/reports/export/csv/standard.py')
    csv_renderer = read('app/reports/export/csv/renderer.py')
    xlsx_schema = read('app/reports/export/xlsx/schema.py')

    assert "TABULAR_EXPORT_STANDARD: Final = 'kaori-tabular-export-v3.0'" in tabular
    assert "TABULAR_SCHEMA_VERSION: Final = '3.0'" in tabular
    assert "CSV_STANDARD: Final = 'kaori-reporting-csv-v3.0'" in csv_standard
    assert "XLSX_REPORTING_STANDARD: Final = 'kaori-reporting-xlsx-v2.0'" in xlsx_schema
    assert "INVENTORY_WORKBOOK_STANDARD: Final = 'kaori-inventory-xlsx-v4.0'" in xlsx_schema
    assert "CSV_INTERCHANGE_PROFILE: Final = 'portable-tabular-v1'" in csv_standard
    assert "CSV_CONTENT_TYPE: Final = 'text/csv; charset=utf-8'" in csv_standard
    assert "'unit'," in csv_standard
    assert 'normalize_analytics_scalar' in csv_renderer


def test_inventory_v4_uses_profile_owned_readable_units_and_executive_summary_contract() -> None:
    schema = read('app/reports/export/xlsx/schema.py')
    profiles = read('app/reports/export/xlsx/profiles_infrastructure.py')
    common = read('app/reports/export/inventory_common.py')
    builder = read('app/reports/export/xlsx/builder.py')
    overview = read('app/reports/export/xlsx/overview.py')

    assert "INVENTORY_OVERVIEW_SHEET: Final = 'Overview'" in schema
    assert 'source_key: str | None = None' in schema
    assert 'scale_divisor: float | None = None' in schema
    assert 'unit: str | None = None' in schema
    assert 'InventoryOverviewChart' in schema
    assert "visual_type: Literal['ranked_bar', 'doughnut']" in schema
    assert 'overview_metrics: tuple[InventoryOverviewMetric, ...]' in schema
    xlsx_standard = read('app/reports/export/xlsx/standard.py')
    assert 'if len(profile.overview_metrics) != 4:' in xlsx_standard
    assert 'if not 1 <= chart.top_n <= 8:' in xlsx_standard
    assert "if chart.visual_type == 'doughnut' and not 2 <= chart.top_n <= 6:" in xlsx_standard
    assert "'usage_gib'" in profiles and "source_key='size_bytes'" in profiles
    assert "'quota_gib'" in profiles and "source_key='quota_bytes'" in profiles
    assert "'Usage Bytes'" not in profiles
    assert "'Quota Bytes'" not in profiles
    assert 'normalize_inventory_row' in common
    assert 'build_inventory_overview_sheet' in builder
    assert "'XLSX Standard'" in builder and 'XLSX_REPORTING_STANDARD' in builder
    standard_import = builder.split('from app.reports.export.xlsx.standard import (', 1)[1].split(')', 1)[0]
    assert 'INVENTORY_OVERVIEW_SHEET,' in standard_import
    assert 'profile.overview_chart' in overview
    assert 'Executive Snapshot' in overview
    assert 'Executive Readout' in overview
    assert 'Primary Visual' in overview
    assert 'Supporting Data' in overview
    assert 'Workbook Navigation' in overview
    assert 'sheet.parent.sheetnames' in overview
    assert 'target_sheet != INVENTORY_OVERVIEW_SHEET' in overview
    assert "cell.hyperlink = f\"#'{target_sheet}'!A1\"" in overview
    assert 'BarChart' in overview and 'DoughnutChart' in overview
    assert 'DataLabelList(showVal=True' in overview
    assert "visual.legend.position = 'b'" in overview
    assert 'showPercent=True' in overview
    assert 'showLegendKey=False' in overview
    assert 'showVal=False' in overview
    assert 'showCatName=False' in overview
    assert 'showSerName=False' in overview
    assert "dLblPos='bestFit'" in overview
    assert 'visual.varyColors = False' in overview
    assert '_safe_text_value(category)' in overview


def test_reporting_docs_and_verifier_reference_v3_contract() -> None:
    reporting = read('docs/reports/kaori-reporting-standard-v1.md')
    verifier = read('scripts/verify_report_generation_contract.py')
    tabular_verifier = read('scripts/verify_tabular_export_standard.py')
    standard = read('docs/reports/kaori-tabular-export-standard-v3.md')

    assert 'kaori-tabular-export-standard-v3.md' in reporting
    assert 'kaori-reporting-csv-v3.0' in reporting
    assert 'kaori-reporting-xlsx-v2.0' in reporting
    assert 'kaori-inventory-xlsx-v4.0' in reporting
    assert '`Overview`, `Inventory`, `Metadata`, and `Field Dictionary`' in reporting
    assert "kaori-reporting-csv-v3.0" in verifier
    assert "kaori-reporting-xlsx-v2.0" in verifier
    assert "kaori-inventory-xlsx-v4.0" in verifier
    assert "kaori-reporting-xlsx-v2.0" in tabular_verifier
    assert 'overview_metrics: tuple[InventoryOverviewMetric, ...]' in tabular_verifier
    assert 'validate_inventory_xlsx_artifact' in tabular_verifier
    assert 'Overview' in standard
    assert 'portable-tabular-v1' in standard
    assert 'standard CSV parsers' in standard
    assert 'CSV' in standard and 'XLSX' in standard


def test_v3_csv_is_self_describing_and_inventory_transforms_support_derived_percentages() -> None:
    tabular = read('app/reports/export/tabular.py')
    csv_standard = read('app/reports/export/csv/standard.py')
    inventory_common = read('app/reports/export/inventory_common.py')
    xlsx_schema = read('app/reports/export/xlsx/schema.py')
    profiles = read('app/reports/export/xlsx/profiles_infrastructure.py')

    assert "'interchange_profile'," in tabular
    assert "interchange_profile: str = ''" in tabular
    assert "CSV_INTERCHANGE_PROFILE" in csv_standard
    assert 'ratio_numerator_key: str | None = None' in xlsx_schema
    assert 'ratio_denominator_key: str | None = None' in xlsx_schema
    assert 'ratio_numerator_key' in inventory_common
    assert 'ratio_denominator_key' in inventory_common
    assert "ratio_numerator_key='size_bytes'" in profiles
    assert "ratio_denominator_key='quota_bytes'" in profiles


def test_xlsx_overview_is_an_executive_landing_page_with_navigation_and_semantic_visuals() -> None:
    overview = read('app/reports/export/xlsx/overview.py')
    standard = read('docs/reports/kaori-tabular-export-standard-v3.md')

    assert "'Executive Snapshot'" in overview
    assert "'Executive Readout'" in overview
    assert "'Primary Visual'" in overview
    assert "'Supporting Data'" in overview
    assert "'Workbook Navigation'" in overview
    assert "cell.hyperlink = f\"#'{target_sheet}'!A1\"" in overview
    assert 'sheet.parent.sheetnames' in overview
    assert 'ranked_bar' in standard
    assert 'doughnut' in standard
    assert 'Executive Snapshot' in standard
    assert 'Executive Readout' in standard
    assert 'Supporting Data' in standard
    assert 'direct value labels' in standard
    assert 'every xlsx report profile' in standard.lower()


def test_xlsx_runtime_artifact_gate_rejects_nonconforming_workbooks() -> None:
    builder = read('app/reports/export/xlsx/builder.py')

    assert 'def validate_inventory_xlsx_artifact(' in builder
    assert 'validate_inventory_xlsx_artifact(output_path)' in builder
    assert 'if workbook.sheetnames != expected_sheets' in builder
    assert "overview['A5'].value != 'Executive Snapshot'" in builder
    assert "overview['A9'].value != 'Executive Readout'" in builder
    assert "overview['A13'].value != 'Primary Visual'" in builder
    assert 'if not overview._charts and not has_no_chart_message' in builder
    assert "getattr(chart, 'varyColors', None) is not False" in builder
    assert "metadata_values.get('Workbook Standard') != INVENTORY_WORKBOOK_STANDARD" in builder
    assert "metadata_values.get('XLSX Standard') != XLSX_REPORTING_STANDARD" in builder
