from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.constants import ANALYTICS_OVERVIEW_SECTION_KEYS
from app.reports.export.html_pdf.builder import build_report_document


@dataclass
class AnalyticsOverviewReportStub:
    id: int = 115
    name: str = 'Analytics Overview Reporting Standard V2.1 Validation'
    report_type: str = 'analytics_overview'
    report_domain: str = 'kubernetes'
    source_kind: str = 'kubernetes'
    cluster_id: str | None = 'cluster-prod'
    namespace: str | None = None
    period: str = '30d'
    output_format: str = 'pdf'
    generated_by_display_name_snapshot: str | None = 'Platform Operations'
    generated_by_username_snapshot: str | None = 'platform-ops'

    def sections_as_list(self) -> list[str]:
        return ['executive_summary', 'resource_snapshot', 'operational_recommendations']


LONG_RESOURCE_NAME = (
    'payments-api-deployment-with-a-very-long-generated-resource-name-'
    'that-is-summarized-in-the-overview-but-remains-complete-in-kaori-detail'
)
LONG_NAMESPACE_NAME = 'payments-production-with-an-extremely-long-namespace-name'
LONG_CLUSTER_NAME = 'Production Kubernetes Cluster With A Long Descriptive Management Name'


def _payload() -> dict[str, object]:
    return {
        'selected_cluster': {'id': 'cluster-prod', 'name': LONG_CLUSTER_NAME},
        'snapshot_summary': {
            'status': 'Current',
            'tone': 'normal',
            'analysis_window': 'Last 30 Days',
            'current_dataset_count': 4,
            'expected_dataset_count': 4,
            'failed_dataset_count': 0,
        },
        'resource_snapshot': {
            'cpu': {'percent': 18.4, 'status': 'Normal', 'tone': 'green'},
            'memory': {'percent': 61.2, 'status': 'Normal', 'tone': 'green'},
            'storage': {'percent': 64.0, 'status': 'Normal', 'tone': 'green'},
            'pods': {'percent': 56.1, 'status': 'Normal', 'tone': 'green'},
        },
        'storage_snapshot': {
            'pvc_requested': '10.0 TB',
            'pvc_used': '6.4 TB',
            'pvc_risk_count': 2,
            'used_percent': 64.0,
            'free_percent': 36.0,
        },
        'forecast_snapshot': {
            'risk_note': 'No near-term threshold breach is projected.',
            'series': [
                {'timestamp': '2026-07-01', 'value': 48.0, 'kind': 'historical'},
                {'timestamp': '2026-07-15', 'value': 59.0, 'kind': 'historical'},
                {'timestamp': '2026-08-01', 'value': 61.2, 'kind': 'historical'},
                {'timestamp': '2026-08-31', 'value': 68.0, 'kind': 'forecast'},
                {'timestamp': '2026-09-30', 'value': 73.0, 'kind': 'forecast'},
            ],
            'memory': {'projected_percent': 73.0, 'threshold_eta': '90 days'},
        },
        'top_consumers': {
            'memory': [
                {
                    'name': LONG_RESOURCE_NAME,
                    'namespace': LONG_NAMESPACE_NAME,
                    'display_value': '18.7%',
                    'percent': 18.7,
                }
            ],
            'cpu': [
                {
                    'name': 'payments-worker-batch-processing-statefulset-with-long-name',
                    'namespace': LONG_NAMESPACE_NAME,
                    'display_value': '12.4%',
                    'percent': 12.4,
                }
            ],
        },
        'actionable_recommendations': {
            'items': [
                {
                    'title': 'Expand low-headroom persistent volumes with long names',
                    'description': 'Expand approved PVCs after validation.',
                    'priority': 'Critical',
                    'source': 'Storage Analysis',
                    'affected_scope': LONG_RESOURCE_NAME,
                }
            ]
        },
        'alerts_snapshot': {'critical': 1, 'warning': 3, 'info': 0},
        'inventory_snapshot': {
            'total_clusters': 1,
            'total_nodes': 5,
            'total_namespaces': 22,
            'total_workloads': 158,
            'total_pods': 412,
            'clusters': [
                {
                    'id': 'cluster-prod',
                    'name': LONG_CLUSTER_NAME,
                    'environment': 'Production',
                    'sync_status_label': 'Current',
                    'sync_status_tone': 'normal',
                    'counts': {'nodes': 5, 'namespaces': 22, 'workloads': 158, 'pods': 412},
                }
            ],
        },
        'data_freshness': {'sources': [], 'issues': []},
    }


def _environment(project_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(project_root / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )


def _rendered_html() -> tuple[object, str, Path]:
    document = build_report_document(AnalyticsOverviewReportStub(), _payload())
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(
        document=document
    )
    return document, rendered_html, project_root


def test_analytics_overview_uses_reporting_standard_v21_and_12_pages() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/analytics_overview.html'
    assert document.metadata['selected_section_keys'] == list(ANALYTICS_OVERVIEW_SECTION_KEYS)
    assert document.presentation['page_count'] == 12
    assert document.presentation['presentation_version'] == 'v2.1-distinct-main-header'
    assert document.presentation['layout_contract'] == {
        'paper': 'A4 Portrait',
        'section_page_breaks': True,
        'truncate_identities': True,
        'identity_policy': 'top-n-summarized',
        'status_style': 'plain-colored-text',
        'visual_style': 'reporting-standard-v2.1',
    }
    assert rendered_html.count('<article class="page') == 12


def test_analytics_overview_uses_management_summary_and_overview_limits() -> None:
    document, rendered_html, _ = _rendered_html()

    summary = document.presentation['executive']['management_summary']
    assert 'highest available shared-resource signal' in summary
    assert 'local storage risk item' in summary
    assert 'What Management Should Know' in rendered_html
    assert 'Top contributors only' in rendered_html
    assert 'complete recommendation register remains available in KAORI' in rendered_html


def test_analytics_overview_title_case_and_section_title_contract() -> None:
    _, rendered_html, _ = _rendered_html()

    for heading in (
        'What Management Should Know',
        'Figure 1 - Memory Demand Forecast',
        'Figure 2 - Leading Consumer Signals',
        'Figure 3 - Report Generation Activity',
        'Figure 5 - Freshness Over Time',
        'Data Sources and Coverage',
        'Known Limitations and Operational Use',
    ):
        assert heading in rendered_html
    assert '<div class="section-index">1</div>' in rendered_html


def test_analytics_overview_status_is_plain_colored_text_without_marker() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.presentation['layout_contract']['status_style'] == 'plain-colored-text'
    assert 'status-dot' not in rendered_html
    assert '::before' not in rendered_html
    assert 'class="status ' in rendered_html


def test_analytics_overview_weasyprint_layout_is_exactly_12_a4_pages() -> None:
    _, rendered_html, project_root = _rendered_html()
    font_config = FontConfiguration()
    rendered_document = HTML(string=rendered_html, base_url=str(project_root)).render(
        stylesheets=[
            CSS(
                filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css'),
                font_config=font_config,
            ),
        ],
        font_config=font_config,
        presentational_hints=True,
    )

    assert len(rendered_document.pages) == 12
    for page in rendered_document.pages:
        assert round(float(page.width), 2) == 793.70
        assert round(float(page.height), 2) == 1122.52


def test_analytics_overview_degraded_metric_is_not_zero_percent() -> None:
    payload = _payload()
    payload['prometheus'] = {
        'status': 'query_degraded',
        'status_label': 'Query Degraded',
        'status_tone': 'critical',
    }
    payload['snapshot_summary'] = {**payload['snapshot_summary'], 'status': 'Failed', 'tone': 'critical'}
    payload['resource_snapshot'] = {
        'cpu': {'percent': 0.0, 'status': 'Normal', 'tone': 'green'},
        'memory': {'percent': 0.0, 'status': 'Normal', 'tone': 'green'},
    }

    document = build_report_document(AnalyticsOverviewReportStub(), payload)
    cpu_metric, memory_metric = document.presentation['executive']['metrics'][:2]

    assert cpu_metric['value'] == 'Not Available'
    assert memory_metric['value'] == 'Not Available'


def test_analytics_overview_css_locks_page_footer_and_table_overflow() -> None:
    _, _, project_root = _rendered_html()
    stylesheet = (
        project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css'
    ).read_text()
    compact = stylesheet.replace(' ', '')

    assert '@page' in stylesheet
    assert 'height:297mm' in compact
    assert 'page-break-after:always' in compact
    assert 'width:210mm' in compact
    assert '.report-header' in stylesheet
    assert 'bottom:5mm' in compact
    assert 'overflow-wrap:anywhere' in compact
    assert 'table-layout:fixed' in compact
    assert 'text-overflow:ellipsis' not in compact


def test_v21_layout_uses_distinct_cover_and_shared_reporting_components() -> None:
    _, rendered_html, _ = _rendered_html()

    assert 'class="page cover"' in rendered_html
    assert 'class="cover-band"' in rendered_html
    assert 'class="report-header"' in rendered_html
    assert 'Priority Findings and Decisions' in rendered_html
    assert 'Resource Key' in rendered_html
    assert 'Data Reliability Guidance' in rendered_html
    assert 'Methodology &amp; Evidence Boundary' in rendered_html


def test_v21_css_has_locked_canvas_and_consistent_vertical_rhythm() -> None:
    _, _, project_root = _rendered_html()
    stylesheet = (
        project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css'
    ).read_text()
    compact = stylesheet.replace(' ', '')

    assert '.cover-band' in stylesheet
    assert '.page-title-row' in stylesheet
    assert '.section-body' in stylesheet
    assert 'margin-top:4.6mm' in compact
    assert 'inset:0' not in compact
    assert 'width:210mm' in compact
    assert '.consumer-chart' in stylesheet
    assert '.page-methodology' in stylesheet
    assert '.page-freshness' in stylesheet


def test_analytics_engine_isolates_approved_stylesheet() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = (
        project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py'
    ).read_text()

    assert "document.template_name == 'reports/pdf/analytics_overview.html'" in source
    assert "stylesheets = [CSS(filename=str(analytics_css_path)" in source
    assert "else:\n        stylesheets = [CSS(filename=str(css_path)" in source


def test_v21_template_uses_approved_content_budgets() -> None:
    _, rendered_html, project_root = _rendered_html()
    template_source = (
        project_root / 'app' / 'templates' / 'reports' / 'pdf' / 'analytics_overview.html'
    ).read_text()

    assert rendered_html.count('<article class="page') == 12
    assert 'p.alerts.alerts[:3]' in template_source
    assert 'p.alerts.anomalies[:2]' in template_source
    assert 'Observations by Recency' not in template_source
    assert 'Data Sources and Methodology' in rendered_html
    assert 'Limitations and Status Language' in rendered_html
