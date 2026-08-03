from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.builder import build_report_document


@dataclass
class ForecastAnalysisReportStub:
    id: int = 411
    name: str = 'Forecast Analysis Publication Validation'
    report_type: str = 'resource_forecast'
    report_domain: str = 'kubernetes'
    source_kind: str = 'prometheus'
    cluster_id: str | None = 'cluster-staging'
    namespace: str | None = None
    period: str = '24h'
    output_format: str = 'pdf'
    generated_by_display_name_snapshot: str | None = 'Platform Operations'
    generated_by_username_snapshot: str | None = 'platform-ops'

    def sections_as_list(self) -> list[str]:
        return [
            'executive_summary',
            'forecast_summary',
            'cpu_forecast',
            'memory_forecast',
            'storage_forecast',
            'pod_forecast',
            'threshold_eta',
            'operational_recommendations',
        ]


def _item(
    key: str,
    current: float,
    projected: float,
    *,
    confidence: str = 'High',
    warning_eta: str = 'Not projected',
) -> dict[str, object]:
    capacity = 100.0
    return {
        'key': key,
        'label': key.title(),
        'unit': '%',
        'has_data': True,
        'capacity': capacity,
        'latest_daily_average': current,
        'latest_daily_average_percent': current,
        'projected_value': projected,
        'projected_percent': projected,
        'signal_quality': confidence,
        'signal_quality_reason': 'Committed history is complete enough for planning review.',
        'warning_eta': {'label': warning_eta, 'days': 204 if warning_eta == '204 days' else None, 'date': None},
        'critical_eta': {'label': 'Not projected', 'days': None, 'date': None},
        'historical_points': [
            {'date': '2026-07-30', 'value': current - 1.0, 'percent': current - 1.0},
            {'date': '2026-08-01', 'value': current - 0.4, 'percent': current - 0.4},
            {'date': '2026-08-03', 'value': current, 'percent': current},
        ],
        'forecast_points': [
            {'date': '2026-08-15', 'value': (current + projected) / 2, 'percent': (current + projected) / 2},
            {'date': '2026-11-01', 'value': projected, 'percent': projected},
        ],
        'method_label': 'Holt-Winters',
    }


def _payload(*, include_storage: bool = False) -> dict[str, object]:
    items = [
        _item('cpu', 1.3, 1.4),
        _item('memory', 53.5, 65.4, warning_eta='204 days'),
        _item('pods', 44.5, 55.4),
    ]
    if include_storage:
        items.append(_item('storage', 60.8, 68.0, confidence='Medium'))
    return {
        'cluster': {
            'id': 'cluster-staging',
            'name': 'K8s PGN Staging',
            'environment': 'Staging',
            'status': 'active',
        },
        'selected_namespace': 'All Namespaces',
        'history_window': '7d',
        'forecast_horizon': '90d',
        'forecast_payload': {
            'has_data': True,
            'history_window': '7d',
            'forecast_horizon': '90d',
            'horizon_days': 90,
            'forecast_method': 'holt_winters',
            'method_label': 'Holt-Winters',
            'generated_at': datetime(2026, 8, 3, 1, 5, tzinfo=UTC),
            'items': items,
            'summary': {
                'total_resources': 4,
                'forecasted_resources': len(items),
                'unavailable_resources': 4 - len(items),
                'warning_count': 0,
                'critical_count': 0,
                'highest_projected_label': 'Memory',
                'highest_projected_percent': 65.4,
            },
            'actionable_recommendations': [
                {
                    'title': 'Review Memory Forecast Direction',
                    'description': 'Validate the long-range memory planning signal.',
                    'priority': 'Warning',
                    'is_actionable': True,
                }
            ],
        },
        'source_evidence': [
            {
                'source': 'Forecast Materialized Snapshot',
                'freshness': '7d',
                'last_collected': '03 Aug 2026 01:05 UTC',
            },
            {
                'source': 'Forecast Projection Evidence',
                'freshness': '90d',
                'last_collected': '03 Aug 2026 01:05 UTC',
            },
            {
                'source': 'Threshold Policy',
                'freshness': '70% / 85%',
                'last_collected': 'Configuration',
            },
        ],
    }


def _environment(project_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(project_root / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )


def _rendered_html(*, include_storage: bool = False) -> tuple[object, str, Path]:
    document = build_report_document(
        ForecastAnalysisReportStub(),
        _payload(include_storage=include_storage),
    )
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(
        document=document
    )
    return document, rendered_html, project_root


def test_forecast_analysis_uses_approved_nine_page_publication() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/forecast_analysis.html'
    assert document.presentation['page_count'] == 9
    assert document.presentation['presentation_version'] == 'v1.1-forecast-analysis-publication'
    contract = document.presentation['layout_contract']
    assert contract['paper'] == 'A4 Portrait'
    assert contract['page_count'] == 9
    assert contract['fixed_page_canvas'] is True
    assert contract['table_policy'] == 'single-line-technical-registers'
    assert contract['missing_evidence_policy'] == 'explicit-not-available'
    assert contract['forecast_policy'] == 'committed-materialized-evidence-only'
    assert contract['cover_header_policy'] == 'symmetric-two-sided'
    assert contract['section_separator_policy'] == 'none'
    assert contract['table_alignment'] == 'left-middle'
    assert contract['methodology_layout'] == 'parallel-registers'
    assert contract['visual_style'] == 'reporting-standard-v2.9.2-analytics-family'
    assert rendered_html.count('<article class="page') == 9


def test_forecast_analysis_keeps_storage_forecast_unavailable_explicit() -> None:
    document, rendered_html, _ = _rendered_html(include_storage=False)

    storage = document.presentation['pod_storage']['storage']['resource']
    assert storage['available'] is False
    assert storage['current_display'] == 'Not Available'
    assert storage['projected_display'] == 'Not Available'
    assert 'Storage forecast evidence is not available.' in rendered_html
    assert 'never converted to zero' in rendered_html


def test_forecast_analysis_derives_memory_projection_and_long_range_eta() -> None:
    document, rendered_html, _ = _rendered_html()

    memory = document.presentation['memory']['resource']
    assert memory['current_display'] == '53.5%'
    assert memory['projected_display'] == '65.4%'
    assert memory['warning_eta'] == '204 days'
    assert '204 days' in rendered_html


def test_forecast_analysis_methodology_uses_side_by_side_boundary_columns() -> None:
    _, rendered_html, project_root = _rendered_html()
    shared = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text(
        encoding='utf-8'
    )

    assert 'class="boundary-columns"' in rendered_html
    assert 'Included in This Report' in rendered_html
    assert 'Not Included in This Report' in rendered_html
    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)' in shared
    assert 'column-gap: 12mm' in shared

def test_forecast_analysis_uses_committed_materialized_collector() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / 'app' / 'reports' / 'export' / 'payloads' / 'forecast.py').read_text(
        encoding='utf-8'
    )

    assert "dataset_key='analytics.forecast'" in source
    assert 'present_forecast_materialized_context' in source
    assert 'ForecastAnalysisService' not in source
    assert 'PrometheusService' not in source


def test_forecast_analysis_stylesheet_is_isolated() -> None:
    project_root = Path(__file__).resolve().parents[2]
    registry = (
        project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'analytics_publication_standard.py'
    ).read_text(encoding='utf-8')
    engine = (project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text(
        encoding='utf-8'
    )

    assert "'reports/pdf/forecast_analysis.html': 'forecast_analysis.css'" in registry
    assert 'ANALYTICS_TEMPLATE_STYLESHEETS' in engine

def test_forecast_analysis_weasyprint_layout_is_exactly_nine_a4_pages(tmp_path: Path) -> None:
    document, rendered_html, project_root = _rendered_html()
    output_path = tmp_path / 'forecast-analysis-validation.pdf'
    font_config = FontConfiguration()

    HTML(string=rendered_html, base_url=str(project_root)).write_pdf(
        target=str(output_path),
        stylesheets=[
            CSS(
                filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'forecast_analysis.css'),
                font_config=font_config,
            ),
            CSS(
                filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css'),
                font_config=font_config,
            ),
        ],
        font_config=font_config,
        presentational_hints=True,
    )

    reader = PdfReader(str(output_path))
    assert len(reader.pages) == 9
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        assert 594 <= width <= 596
        assert 841 <= height <= 843
