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
    name: str = 'Analytics Overview Long Name Validation'
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


def _payload() -> dict[str, object]:
    return {
        'selected_cluster': {
            'id': 'cluster-prod',
            'name': 'Production Kubernetes Cluster With A Long Descriptive Name',
        },
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
                    'name': 'Production Kubernetes Cluster With A Long Descriptive Name',
                    'sync_status_label': 'Current',
                    'sync_status_tone': 'normal',
                    'counts': {
                        'nodes': 5,
                        'namespaces': 22,
                        'workloads': 158,
                        'pods': 412,
                    },
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


def test_analytics_overview_uses_canonical_12_page_template_and_preserves_long_names() -> None:
    report = AnalyticsOverviewReportStub()
    document = build_report_document(report, _payload())
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(document=document)

    assert document.template_name == 'reports/pdf/analytics_overview.html'
    assert document.metadata['selected_section_keys'] == list(ANALYTICS_OVERVIEW_SECTION_KEYS)
    assert document.presentation['page_count'] == 12
    assert rendered_html.count('<section class="ao-page') == 12
    assert LONG_RESOURCE_NAME in rendered_html
    assert LONG_NAMESPACE_NAME in rendered_html
    assert 'text-overflow: ellipsis' not in (
        project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css'
    ).read_text()


def test_analytics_overview_weasyprint_layout_stays_exactly_12_pages() -> None:
    report = AnalyticsOverviewReportStub()
    document = build_report_document(report, _payload())
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(document=document)
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
