from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_v3_registry_covers_every_analytics_pdf_template() -> None:
    source = read('app/reports/export/html_pdf/analytics_publication_standard.py')
    module = ast.parse(source)
    registry = None
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == 'ANALYTICS_TEMPLATE_STYLESHEETS':
                registry = ast.literal_eval(node.value)
                break

    assert registry == {
        'reports/pdf/analytics_overview.html': 'analytics_overview.css',
        'reports/pdf/resource_utilization.html': 'resource_utilization.css',
        'reports/pdf/capacity_analysis.html': 'capacity_analysis.css',
        'reports/pdf/storage_analysis.html': 'storage_analysis.css',
        'reports/pdf/workload_analysis.html': 'workload_analysis.css',
        'reports/pdf/forecast_analysis.html': 'forecast_analysis.css',
        'reports/pdf/top_consumers_analysis.html': 'top_consumers_analysis.css',
        'reports/pdf/alerts_anomalies.html': 'alerts_anomalies.css',
        'reports/pdf/analytics_unavailable.html': 'analytics_unavailable.css',
    }


def test_legacy_generic_publication_is_removed() -> None:
    for path in (
        'app/templates/reports/pdf/report.html',
        'app/templates/reports/pdf/components/_reporting_standard.html',
        'app/static/reports/pdf/report.css',
        'app/static/reports/pdf/reporting_standard.css',
    ):
        assert not (ROOT / path).exists(), path


def test_publication_css_owns_typography_rhythm_and_safe_tables() -> None:
    css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())

    assert 'KAORIAnalyticsPDFPublicationStandardv3.0' in compact
    assert 'font-family:"InterAnalytics","DejaVuSans",Arial,sans-serif' in compact
    assert 'font-size:8pt' in compact
    assert 'line-height:1.46' in compact
    assert 'table-layout:fixed' in compact
    assert 'vertical-align:middle' in compact
    assert 'overflow-wrap:break-word' in compact
    assert 'text-overflow:ellipsis' not in compact
    assert 'word-break:break-all' not in compact


def test_dynamic_identity_reports_use_reference_registers() -> None:
    for path in (
        'app/templates/reports/pdf/analytics_overview.html',
        'app/templates/reports/pdf/resource_utilization.html',
        'app/templates/reports/pdf/storage_analysis.html',
        'app/templates/reports/pdf/workload_analysis.html',
        'app/templates/reports/pdf/top_consumers_analysis.html',
        'app/templates/reports/pdf/alerts_anomalies.html',
    ):
        source = read(path)
        assert 'identity-register' in source or 'identity_register(' in source, path
        assert 'complete' in source.lower() or 'identity references' in source.lower(), path


def test_chart_collision_resolver_is_used_by_multi_series_reports() -> None:
    helper = read('app/reports/export/html_pdf/chart_labels.py')
    assert 'def resolve_vertical_labels(' in helper
    assert 'min_gap' in helper
    assert 'dedicated label gutter' in helper.lower()

    for path in (
        'app/reports/export/html_pdf/forecast_analysis.py',
        'app/reports/export/html_pdf/resource_utilization.py',
        'app/reports/export/html_pdf/capacity_analysis.py',
    ):
        assert 'resolve_vertical_labels' in read(path), path


def test_memory_values_are_normalized_before_presentation() -> None:
    resource = read('app/reports/export/html_pdf/resource_utilization.py')
    overview = read('app/reports/export/html_pdf/analytics_overview.py')

    assert 'return value / 1024**3' in resource
    assert 'raw_value = raw_value / 1024**3' in overview


def test_every_analytics_type_has_a_public_reference_code() -> None:
    source = read('app/reports/reference.py')
    expected = {
        'analytics_overview': 'AOV',
        'resource_utilization': 'RUT',
        'capacity_analysis': 'CAP',
        'storage_analysis': 'STO',
        'workload_analysis': 'WLA',
        'resource_forecast': 'FCT',
        'top_consumers': 'TPC',
        'alerts_anomalies': 'ALA',
    }
    for report_type, code in expected.items():
        assert f"'{report_type}': '{code}'" in source
    assert "return f'KAORI-{family_code}-{type_code}-{date_code}-{fingerprint}'" in source


def test_unavailable_sources_use_the_canonical_analytics_publication() -> None:
    builder = read('app/reports/export/html_pdf/builder.py')
    template = read('app/templates/reports/pdf/analytics_unavailable.html')

    assert "template_name = 'reports/pdf/analytics_unavailable.html'" in builder
    assert 'No analytical conclusion is produced from unavailable evidence.' in template
    assert 'Source Availability' in template
    assert 'Recovery and Generation Controls' in template


def test_publication_verifier_is_a_static_quality_gate() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    verifier = read('scripts/verify_analytics_pdf_publication.py')

    assert 'python scripts/verify_analytics_pdf_publication.py' in quality_gate
    assert 'KAORI Analytics PDF Publication v3 audit passed' in verifier
