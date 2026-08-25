from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_analytics_is_management_overview_not_inventory_dump() -> None:
    builder = read('app/reports/export/html_pdf/object_storage_analysis.py')
    template = read('app/templates/reports/pdf/object_storage_analysis.html')

    assert "inventory_detail_policy='excluded-from-analytics-pdf'" in builder
    assert 'bucket_rows[:5]' in builder
    assert "_sequence(payload.get('risk_findings'))[:4]" in builder
    assert "'presentation_version': 'v3.0-object-storage-overview-standard'" in builder

    assert "'report_title': 'Object Storage Analytics Overview'" in builder
    assert 'ui.cover_title(p.report_title' in template
    assert 'single-line-register' in template
    assert 'Consumer Identity References' in template
    assert 'Object Storage Inventory' in template
    assert 'document.sections' not in template
    assert 'ui.technical_table(' not in template


def test_multi_series_chart_labels_have_a_reserved_right_gutter() -> None:
    forecast = read('app/reports/export/html_pdf/forecast_analysis.py')
    resource = read('app/reports/export/html_pdf/resource_utilization.py')
    capacity = read('app/reports/export/html_pdf/capacity_analysis.py')

    assert 'left, top, chart_w, chart_h = 58.0, 24.0, 520.0, 160.0' in forecast
    assert 'label_line_x = 626.0' in forecast
    assert 'label_x = width - 18.0' in forecast
    assert 'text-anchor="end" font-size="10.5"' in forecast

    assert 'left, right, top, bottom = 58, 92, 20, 45' in resource
    assert 'label_x = width - 70' in resource
    assert 'label_x - 7' in resource
    assert 'style="font:12px Inter,sans-serif' in resource

    assert 'left, right, top, bottom = 58, 165, 22, 40' in capacity
    assert 'label_line_x = width - 166' in capacity
    assert 'label_x = width - 18' in capacity
    assert 'text-anchor="end" style="font:11px Inter,sans-serif' in capacity
    assert 'width="{width - 2}" height="{height - 2}"' in capacity


def test_dense_storage_and_workload_pages_defer_detail_to_reference_blocks() -> None:
    storage = read('app/reports/export/html_pdf/storage_analysis.py')
    workload_css = read('app/static/reports/pdf/workload_analysis.css')

    assert "'pv_rows': _pv_records(pv_rows)[:2]" in storage
    assert "'pvc_rows': _pvc_records(pvc_rows)[:2]" in storage

    assert '.signal-table th:first-child,' in workload_css
    assert '.signal-table th:nth-child(2) { width: 53%; }' in workload_css
    assert '.signal-table td:nth-child(2)' in workload_css
    assert 'white-space: normal;' in workload_css
    assert 'overflow-wrap: break-word;' in workload_css


def test_publication_standard_documents_management_readability_and_canvas_safety() -> None:
    standard = read('docs/reports/kaori-analytics-pdf-publication-standard-v3.md')

    assert 'Management readability and canvas safety' in standard
    assert 'one to one-and-a-half paragraph' in standard
    assert 'stable reference code' in standard
    assert 'dedicated right-side label gutter' in standard
    assert 'analytics report is a management and operational summary' in standard
    assert 'inventory publication owns exhaustive object-level detail' in standard
