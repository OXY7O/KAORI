from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _report_block(catalog: str, report_type: str) -> str:
    pattern = rf'(?ms)^- value: {re.escape(report_type)}\n(?P<body>.*?)(?=^- value: |\Z)'
    match = re.search(pattern, catalog)
    assert match is not None, report_type
    return match.group(0)


def test_every_published_analytics_report_allows_pdf_xlsx_csv_with_pdf_default() -> None:
    catalog = read('app/definitions/catalogs/reports/catalog.yaml')
    analytics_types = (
        'analytics_overview',
        'resource_utilization',
        'capacity_analysis',
        'storage_analysis',
        'workload_analysis',
        'resource_forecast',
        'top_consumers',
        'alerts_anomalies',
        'object_storage_analysis',
    )

    for report_type in analytics_types:
        block = _report_block(catalog, report_type)
        assert 'family: analytics' in block
        assert 'default_format: pdf' in block
        assert re.search(r'allowed_formats:\n\s+- pdf\n\s+- xlsx\n\s+- csv', block)


def test_reports_pages_publish_analytics_excel_as_analysis_artifact() -> None:
    readme = read('app/reports/README.md')
    presentation = read('app/reports/overview/presentation.py')
    service = read('app/reports/overview/service.py')
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')
    coverage = read('app/templates/reports/overview/partials/_reporting_coverage.html')
    pipeline = read('app/templates/reports/overview/partials/_coverage_pipeline_workspace.html')
    templates_service = read('app/reports/report_templates/service.py')
    generate_page = read('app/templates/reports/generate/index.html')
    generate_runtime = read('app/static/js/reports/generate.js')
    generated_service = read('app/reports/generated/service.py')
    generated_page = read('app/templates/reports/generated/index.html')
    generated_detail = read('app/templates/reports/generated/detail.html')
    schedules_service = read('app/reports/schedules/service.py')
    schedules_page = read('app/templates/reports/schedules/index.html')
    storage_service = read('app/reports/storage/service.py')
    storage_page = read('app/templates/reports/storage/index.html')

    assert 'Analytics: PDF, XLSX, or CSV; PDF is the default.' in readme
    assert "'formats': ['PDF', 'XLSX', 'CSV']" in presentation
    assert "'formats': ['PDF', 'XLSX', 'CSV']" in service
    assert 'PDF · XLSX · CSV' in estate
    assert 'analytics uses PDF/XLSX/CSV' in coverage
    assert 'stored PDF, XLSX, or CSV artifact' in pipeline
    assert 'Analytics PDF/XLSX/CSV or Inventory Excel/CSV renderer' in templates_service

    # Generate template owns declarative format controls; the static runtime owns dynamic purpose copy.
    assert 'XLSX Workbook' in generate_page
    assert 'Governed analytical workbook for drill-down, filtering, trends, and evidence review.' in generate_runtime

    # Every Reports operating page must explain the newly supported Analytics workbook artifact.
    assert 'PDF publications, XLSX analytical workbooks, and CSV exports' in generated_service
    assert 'PDF · XLSX · CSV Artifacts' in generated_page
    assert 'Analytics XLSX is a drill-down analysis artifact' in generated_detail
    assert 'Analytics PDF, XLSX, or CSV artifacts' in schedules_service
    assert 'Analytics schedules may publish PDF, XLSX, or CSV' in schedules_page
    assert 'PDF/XLSX/CSV artifacts' in storage_service
    assert 'PDF · XLSX · CSV Artifacts' in storage_page


def test_analytics_xlsx_family_standard_and_dispatch_are_documented_and_verifiable() -> None:
    reporting_standard = read('docs/reports/kaori-reporting-standard-v1.md')
    tabular_standard = read('docs/reports/kaori-tabular-export-standard-v3.md')
    artifacts = read('app/reports/export/artifacts.py')
    xlsx_renderer = read('app/reports/export/xlsx/renderer.py')

    assert 'kaori-analytics-xlsx-v1.0' in reporting_standard
    assert 'Analytics XLSX' in tabular_standard
    assert 'from app.reports.export.xlsx.renderer import render_report_xlsx' in artifacts
    assert 'FORMAT_XLSX: render_report_xlsx' in artifacts
    assert 'def render_report_xlsx(' in xlsx_renderer
    assert 'REPORT_FAMILY_ANALYTICS' in xlsx_renderer
    assert 'build_analytics_workbook' in xlsx_renderer
    assert 'collect_report_payload' in xlsx_renderer

    generation_verifier = read('scripts/verify_report_generation_contract.py')
    tabular_verifier = read('scripts/verify_tabular_export_standard.py')
    assert "ANALYTICS_FORMATS = {'pdf', 'xlsx', 'csv'}" in generation_verifier
    assert 'FORMAT_XLSX: render_report_xlsx' in generation_verifier
    assert 'ANALYTICS_WORKBOOK_PROFILES' in generation_verifier
    assert 'ANALYTICS_WORKBOOK_STANDARD' in tabular_verifier
    assert 'analytics_builder.py' in tabular_verifier
    assert 'analytics_overview.py' in tabular_verifier
