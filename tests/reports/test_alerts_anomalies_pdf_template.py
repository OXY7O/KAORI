from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.alerts_anomalies import build_alerts_anomalies_presentation

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _payload() -> dict[str, object]:
    alerts = [
        {
            'name': 'KubePodNotReady',
            'severity': 'warning',
            'status': 'firing',
            'namespace': 'url-shortener-staging',
            'starts_at_display': '25 Jul 2026 10:11 UTC',
            'labels': {'category': 'Resource'},
            'summary': 'Pod has been in a non-ready state.',
        },
        {
            'name': 'KubeHpaMaxedOut',
            'severity': 'warning',
            'status': 'firing',
            'namespace': 'pgnmobile-staging',
            'starts_at_display': '25 Jul 2026 10:25 UTC',
            'labels': {'category': 'Capacity'},
            'summary': 'HPA remains at its configured maximum.',
        },
        {
            'name': 'KubeDeploymentReplicasMismatch',
            'severity': 'warning',
            'status': 'firing',
            'namespace': 'url-shortener-staging',
            'starts_at_display': '25 Jul 2026 10:25 UTC',
            'labels': {'category': 'Availability'},
            'summary': 'Deployment replicas do not match desired state.',
        },
    ]
    anomalies = [
        {'name': 'Pod Restart Spike', 'namespace': 'pgnmobile-staging', 'severity': 'warning'},
        {'name': 'Pod Restart Spike', 'namespace': 'logging', 'severity': 'warning'},
    ]
    return {
        'cluster': {'environment': 'Staging'},
        'summary': {'active_alerts': 3, 'critical_alerts': 0, 'warning_alerts': 3, 'detected_anomalies': 2},
        'selected_cluster_signal_overview': {'info_alerts': 0},
        'alerts': alerts,
        'anomalies': anomalies,
        'source_status': {'label': 'Alertmanager Connected', 'response_time_ms': 25},
        'anomaly_source_status': {'label': 'Prometheus Anomaly Evidence', 'partial': True},
        'actionable_recommendations': [],
    }


def _presentation() -> dict[str, object]:
    return build_alerts_anomalies_presentation(
        SimpleNamespace(),
        _payload(),
        report_id='502',
        report_name='Alerts and Anomalies Validation',
        cluster_scope='K8s PGN Staging',
        namespace_scope='All Namespaces',
        period_label='Last 24 Hours',
        data_cutoff='03 Aug 2026 01:06 UTC',
        generated_at='03 Aug 2026 01:06 UTC',
        generated_by='Platform Operations',
        classification='Internal',
    )


def _rendered_html() -> str:
    environment = Environment(
        loader=FileSystemLoader(PROJECT_ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    document = SimpleNamespace(
        report_name='Alerts and Anomalies Validation',
        presentation=_presentation(),
    )
    return environment.get_template('reports/pdf/alerts_anomalies.html').render(document=document)


def test_alerts_anomalies_presentation_uses_nine_page_contract() -> None:
    presentation = _presentation()

    assert presentation['presentation_version'] == 'v3.0-alerts-anomalies-publication'
    assert presentation['page_count'] == 9
    assert presentation['layout_contract']['correlation_policy'] == 'review-lead-not-causality'


def test_alerts_anomalies_keeps_missing_anomaly_support_explicit() -> None:
    presentation = _presentation()
    rendered_html = _rendered_html()

    assert presentation['anomalies']['metrics'][2]['value'] == '0'
    assert all(row['evidence'] == 'Not Available' for row in presentation['anomalies']['rows'])
    assert 'Missing supporting evidence must not be translated into no anomaly or no impact.' in rendered_html


def test_alerts_anomalies_derives_category_coverage_without_forced_labels() -> None:
    presentation = _presentation()

    assert presentation['severity_category']['metrics'][1]['value'] == '3'
    assert presentation['severity_category']['metrics'][2]['value'] == '0'
    assert presentation['severity_category']['metrics'][3]['value'] == '100.0%'


def test_alerts_anomalies_methodology_uses_side_by_side_boundary_columns() -> None:
    rendered_html = _rendered_html()
    shared = (PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text(
        encoding='utf-8'
    )

    assert 'class="boundary-columns"' in rendered_html
    assert 'Included in This Report' in rendered_html
    assert 'Not Included in This Report' in rendered_html
    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)' in shared
    assert 'column-gap: 12mm' in shared


def test_alerts_anomalies_renderer_registration_is_present() -> None:
    builder = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'builder.py').read_text(encoding='utf-8')
    registry = (
        PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'analytics_publication_standard.py'
    ).read_text(encoding='utf-8')
    engine = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text(encoding='utf-8')

    assert "report.report_type == 'alerts_anomalies'" in builder
    assert "'reports/pdf/alerts_anomalies.html': 'alerts_anomalies.css'" in registry
    assert 'ANALYTICS_TEMPLATE_STYLESHEETS' in engine


def test_alerts_anomalies_weasyprint_layout_is_exactly_nine_a4_pages(tmp_path: Path) -> None:
    output_path = tmp_path / 'alerts-anomalies-validation.pdf'
    font_config = FontConfiguration()
    HTML(string=_rendered_html(), base_url=str(PROJECT_ROOT)).write_pdf(
        target=str(output_path),
        stylesheets=[
            CSS(
                filename=str(PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'alerts_anomalies.css'),
                font_config=font_config,
            ),
            CSS(
                filename=str(PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css'),
                font_config=font_config,
            ),
        ],
        font_config=font_config,
        presentational_hints=True,
    )

    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 9
    for page in reader.pages:
        assert 594 <= float(page.mediabox.width) <= 596
        assert 841 <= float(page.mediabox.height) <= 843
