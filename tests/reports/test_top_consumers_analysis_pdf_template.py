from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.top_consumers_analysis import build_top_consumers_analysis_presentation


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _payload() -> dict[str, object]:
    rows = [
        {
            'identity': {'primary': 'integration-service-575957488f-zp4fj'},
            'namespace': 'billing-pgnbilling-staging',
            'resource_type': 'cpu',
            'resource_label': 'CPU',
            'current_usage': 0.20,
            'current_display': '0.20 cores',
            'pressure_display': 'Not Available',
            'risk': {'key': 'warning', 'label': 'Review'},
        },
        {
            'identity': {'primary': 'prometheus-prometheus-kube-prometheus-prometheus-0'},
            'namespace': 'monitoring',
            'resource_type': 'cpu',
            'current_usage': 0.19,
            'current_display': '0.19 cores',
            'risk': {'key': 'warning', 'label': 'Review'},
        },
        {
            'identity': {'primary': 'kube-apiserver-k8s-master-staging-001.pgn.co.id'},
            'namespace': 'kube-system',
            'resource_type': 'cpu',
            'current_usage': 0.14,
            'current_display': '0.14 cores',
            'risk': {'key': 'normal', 'label': 'Normal'},
        },
        {
            'identity': {'primary': 'cstor-disk-thkc-55cf8fb6fb-zfz2k'},
            'namespace': 'openebs',
            'resource_type': 'memory',
            'current_usage': 16.39,
            'current_display': '16.39 GiB',
            'risk': {'key': 'warning', 'label': 'Review'},
        },
        {
            'identity': {'primary': 'cstor-disk-dfgm-7f4dfcd7cd-58w7w'},
            'namespace': 'openebs',
            'resource_type': 'memory',
            'current_usage': 15.94,
            'current_display': '15.94 GiB',
            'risk': {'key': 'warning', 'label': 'Review'},
        },
        {
            'identity': {'primary': 'cstor-disk-qmnr-66bddf495-bs5b6'},
            'namespace': 'openebs',
            'resource_type': 'memory',
            'current_usage': 15.45,
            'current_display': '15.45 GiB',
            'risk': {'key': 'warning', 'label': 'Review'},
        },
    ]
    return {
        'cluster': {'environment': 'Staging'},
        'prometheus_status': {'connected': True, 'response_time_ms': 405},
        'consumer_payload': {
            'rows': rows,
            'coverage': {'complete_count': 2, 'partial_count': 1, 'unavailable_count': 1},
            'actionable_recommendations': [],
        },
    }


def _presentation() -> dict[str, object]:
    return build_top_consumers_analysis_presentation(
        SimpleNamespace(),
        _payload(),
        report_id='501',
        report_name='Top Consumers Validation',
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
        report_name='Top Consumers Validation',
        presentation=_presentation(),
    )
    return environment.get_template('reports/pdf/top_consumers_analysis.html').render(document=document)


def test_top_consumers_presentation_uses_nine_page_contract() -> None:
    presentation = _presentation()

    assert presentation['presentation_version'] == 'v1.0-top-consumers-publication'
    assert presentation['page_count'] == 9
    assert presentation['layout_contract']['ranking_policy'] == 'displayed-set-share-per-resource'


def test_top_consumers_recomputes_displayed_cpu_share_from_published_rows() -> None:
    presentation = _presentation()
    rows = presentation['cpu']['rows']

    assert rows[0]['displayed_share_label'] == '37.7%'
    assert rows[1]['displayed_share_label'] == '35.8%'
    assert rows[2]['displayed_share_label'] == '26.4%'
    assert round(sum(row['displayed_share'] for row in rows), 1) == 100.0


def test_top_consumers_keeps_memory_values_normalized_and_single_line() -> None:
    presentation = _presentation()
    rendered_html = _rendered_html()

    assert presentation['memory']['metrics'][1]['value'] == '47.78 GiB'
    assert '16.39 GiB' in rendered_html
    assert '15.94 GiB' in rendered_html
    assert '15.45 GiB' in rendered_html


def test_top_consumers_methodology_uses_side_by_side_boundary_columns() -> None:
    rendered_html = _rendered_html()
    css = (PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'top_consumers_analysis.css').read_text(encoding='utf-8')

    assert 'class="boundary-columns"' in rendered_html
    assert 'Included in This Report' in rendered_html
    assert 'Not Included in This Report' in rendered_html
    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)' in css
    assert 'column-gap: 14mm' in css


def test_top_consumers_renderer_registration_is_present() -> None:
    builder = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'builder.py').read_text(encoding='utf-8')
    engine = (PROJECT_ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text(encoding='utf-8')

    assert "report.report_type == 'top_consumers'" in builder
    assert "'reports/pdf/top_consumers_analysis.html': 'top_consumers_analysis.css'" in engine


def test_top_consumers_weasyprint_layout_is_exactly_nine_a4_pages(tmp_path: Path) -> None:
    output_path = tmp_path / 'top-consumers-validation.pdf'
    font_config = FontConfiguration()
    HTML(string=_rendered_html(), base_url=str(PROJECT_ROOT)).write_pdf(
        target=str(output_path),
        stylesheets=[
            CSS(
                filename=str(PROJECT_ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'top_consumers_analysis.css'),
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
