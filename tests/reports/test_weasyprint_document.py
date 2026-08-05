from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.export.html_pdf.builder import build_report_document
from app.reports.export.html_pdf.engine import render_document_pdf


@dataclass
class ReportStub:
    id: int = 91
    name: str = 'Production Capacity Report'
    report_type: str = 'resource_forecast'
    report_domain: str = 'kubernetes'
    source_kind: str = 'kubernetes'
    cluster_id: str | None = 'cluster-prod'
    namespace: str | None = None
    period: str = '30d'
    output_format: str = 'pdf'
    generated_by_display_name_snapshot: str | None = 'Platform Operations'
    generated_by_username_snapshot: str | None = 'platform-ops'

    def sections_as_list(self) -> list[str]:
        return [
            'executive_summary',
            'forecast_summary',
            'cpu_forecast',
            'operational_recommendations',
        ]


def build_payload() -> dict[str, object]:
    return {
        'cluster': {
            'id': 'cluster-prod',
            'name': 'Production Cluster',
            'environment': 'Production',
            'status': 'Ready',
        },
        'prometheus_status': {
            'label': 'Ready',
            'description': 'Prometheus analytics source is available.',
        },
        'forecast_payload': {
            'summary': {
                'total_resources': 2,
                'warning_count': 0,
                'critical_count': 1,
                'highest_projected_label': 'Memory',
                'highest_projected_percent': 92,
                'status': 'Needs Review',
            },
            'items': [
                {
                    'key': 'cpu',
                    'label': 'CPU',
                    'current_percent': 52,
                    'projected_percent': 68,
                    'status_label': 'Normal',
                },
                {
                    'key': 'memory',
                    'label': 'Memory',
                    'current_percent': 71,
                    'projected_percent': 92,
                    'status_label': 'Critical',
                },
            ],
            'actionable_recommendations': [
                {
                    'title': 'Increase memory headroom',
                    'description': 'Add capacity before the projected critical threshold.',
                    'priority': 'Critical',
                }
            ],
        },
    }


def test_document_preserves_existing_template_section_order() -> None:
    report = ReportStub()
    document = build_report_document(report, build_payload())

    assert [section.key for section in document.sections] == report.sections_as_list()
    assert document.template_label == 'Resource Forecast Template'
    assert document.renderer_label == 'WeasyPrint HTML/PDF'
    assert document.overall_tone == 'critical'


def test_unavailable_payload_hides_technical_endpoint_details() -> None:
    report = ReportStub()
    document = build_report_document(
        report,
        {
            '_error': (
                "HTTPSConnectionPool(host='internal-prometheus.example', port=443): "
                'Max retries exceeded with url: /api/v1/query?query=secret'
            )
        },
    )

    rendered = ' '.join(
        finding.description
        for section in document.sections
        for finding in section.findings
    )
    assert 'internal-prometheus.example' not in rendered
    assert '/api/v1/query' not in rendered
    assert 'temporarily unreachable' in rendered


def test_weasyprint_engine_creates_pdf(tmp_path: Path) -> None:
    report = ReportStub()
    document = build_report_document(report, build_payload())
    project_root = Path(__file__).resolve().parents[2]
    environment = Environment(
        loader=FileSystemLoader(project_root / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    output_path = tmp_path / 'report.pdf'

    render_document_pdf(
        document,
        output_path,
        template_environment=environment,
        css_path=project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css',
        base_url=project_root,
        metadata={'pdf_identifier': 'test-report'},
    )

    assert output_path.read_bytes().startswith(b'%PDF-')
    assert output_path.stat().st_size > 10_000
