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
    id: int = 108
    name: str = 'Analytics Overview Management Standard Validation'
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
        # Existing generated reports may still hold the legacy five-section list.
        return [
            'executive_summary',
            'analytics_summary',
            'resource_snapshot',
            'risk_overview',
            'operational_recommendations',
        ]


LONG_RESOURCE_NAME = (
    'payments-api-deployment-with-a-very-long-generated-resource-name-'
    'that-must-remain-complete-7d8f7d8f7d'
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
            'cpu': {'percent': 58.4, 'status': 'Normal', 'tone': 'green'},
            'memory': {'percent': 71.2, 'status': 'Warning', 'tone': 'amber'},
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
            'series': [
                {'timestamp': '2026-07-01', 'value': 48.0, 'kind': 'historical'},
                {'timestamp': '2026-07-15', 'value': 59.0, 'kind': 'historical'},
                {'timestamp': '2026-08-01', 'value': 71.2, 'kind': 'historical'},
                {'timestamp': '2026-08-31', 'value': 82.0, 'kind': 'forecast'},
                {'timestamp': '2026-09-30', 'value': 91.0, 'kind': 'forecast'},
            ],
            'memory': {'projected_percent': 91.0, 'threshold_eta': '56 days'},
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
                    'environment': 'Production Environment With A Descriptive Name',
                    'sync_status_label': 'Current',
                    'sync_status_tone': 'normal',
                    'counts': {'nodes': 5, 'namespaces': 22, 'workloads': 158, 'pods': 412},
                }
            ],
        },
        'data_freshness': {
            'sources': [
                {
                    'label': 'Metrics',
                    'source': 'Prometheus Observation Cache',
                    'type': 'Metrics Cache',
                    'last_successful': '01/08/2026 05:20 WIB',
                    'freshness': '132 ms',
                    'status': 'Ready',
                    'tone': 'normal',
                }
            ],
            'issues': [],
        },
    }


def _environment(project_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(project_root / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )


def _rendered_html() -> tuple[object, str, Path]:
    report = AnalyticsOverviewReportStub()
    document = build_report_document(report, _payload())
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(
        document=document
    )
    return document, rendered_html, project_root


def test_analytics_overview_uses_v6_management_standard_and_12_authored_pages() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/analytics_overview.html'
    assert document.metadata['selected_section_keys'] == list(ANALYTICS_OVERVIEW_SECTION_KEYS)
    assert document.presentation['page_count'] == 12
    assert document.presentation['presentation_version'] == 'v6-management-standard'
    assert document.presentation['layout_contract'] == {
        'paper': 'A4 Portrait',
        'section_page_breaks': True,
        'truncate_identities': False,
        'status_style': 'plain-colored-text',
    }
    assert rendered_html.count('<section class="page') == 12


def test_analytics_overview_preserves_long_names_with_reference_maps() -> None:
    _, rendered_html, project_root = _rendered_html()
    stylesheet = (
        project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css'
    ).read_text()

    assert LONG_RESOURCE_NAME in rendered_html
    assert LONG_NAMESPACE_NAME in rendered_html
    assert LONG_CLUSTER_NAME in rendered_html
    assert 'Full Resource Identities' in rendered_html
    assert 'Full Affected Scope' in rendered_html
    assert 'Full Schedule Names' in rendered_html
    assert 'Full Report Names' in rendered_html
    assert 'Full Cluster Identities' in rendered_html
    assert 'text-overflow: ellipsis' not in stylesheet
    assert 'hyphens:none' in stylesheet.replace(' ', '')
    assert 'overflow-wrap:anywhere' in stylesheet.replace(' ', '')


def test_analytics_overview_uses_plain_colored_status_text_without_marker_dots() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.presentation['layout_contract']['status_style'] == 'plain-colored-text'
    assert 'status-dot' not in rendered_html
    assert 'ao-status-dot' not in rendered_html
    assert '<span class="status ' in rendered_html


def test_analytics_overview_forecast_chart_uses_bounded_v6_management_plot() -> None:
    document, _, _ = _rendered_html()
    chart = document.presentation['trend_forecast']['chart_svg']

    assert 'viewBox="0 0 800 230"' in chart
    assert 'Projected demand' in chart
    assert 'Warning 70%' in chart
    assert 'Critical 85%' in chart


def test_analytics_overview_weasyprint_layout_stays_exactly_12_a4_pages() -> None:
    _, rendered_html, project_root = _rendered_html()
    font_config = FontConfiguration()

    rendered_document = HTML(string=rendered_html, base_url=str(project_root)).render(
        stylesheets=[
            CSS(
                filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'report.css'),
                font_config=font_config,
            ),
            CSS(
                filename=str(
                    project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css'
                ),
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


def test_analytics_overview_does_not_present_degraded_metrics_as_zero_percent() -> None:
    report = AnalyticsOverviewReportStub()
    payload = _payload()
    payload['prometheus'] = {
        'status': 'query_degraded',
        'status_label': 'Query Degraded',
        'status_tone': 'critical',
    }
    payload['snapshot_summary'] = {
        **payload['snapshot_summary'],
        'status': 'Failed',
        'tone': 'critical',
    }
    payload['resource_snapshot'] = {
        'cpu': {'percent': 0.0, 'status': 'Normal', 'tone': 'green'},
        'memory': {'percent': 0.0, 'status': 'Normal', 'tone': 'green'},
    }

    document = build_report_document(report, payload)
    cpu_metric, memory_metric = document.presentation['executive']['metrics'][:2]

    assert cpu_metric['value'] == 'Not Available'
    assert memory_metric['value'] == 'Not Available'
    assert cpu_metric['status'] in {'Query Degraded', 'Failed'}
    assert memory_metric['status'] in {'Query Degraded', 'Failed'}


def test_analytics_overview_css_enforces_page_boundaries_and_footer_contract() -> None:
    _, _, project_root = _rendered_html()
    stylesheet = (
        project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css'
    ).read_text()

    assert 'box-sizing: border-box' in stylesheet
    assert 'page-break-after:always' in stylesheet.replace(' ', '')
    assert '@page' in stylesheet
    assert 'bottom:5mm' in stylesheet.replace(' ', '')
    assert 'body.ao-v6 .cover-header { height:110mm; }' in stylesheet
    assert '.inventory-main .mix-row' in stylesheet
