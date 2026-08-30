from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.builder import build_report_document


@dataclass
class CapacityAnalysisReportStub:
    id: int = 236
    name: str = 'Capacity Analysis Publication Validation'
    report_type: str = 'capacity_analysis'
    report_domain: str = 'kubernetes'
    source_kind: str = 'kubernetes'
    cluster_id: str | None = 'cluster-staging'
    namespace: str | None = None
    period: str = '24h'
    output_format: str = 'pdf'
    generated_by_display_name_snapshot: str | None = 'Platform Operations'
    generated_by_username_snapshot: str | None = 'platform-ops'

    def sections_as_list(self) -> list[str]:
        return [
            'executive_summary',
            'worker_capacity_summary',
            'resource_allocation_headroom',
            'capacity_pressure_risk',
            'operational_recommendations',
        ]


def _payload(*, include_forecast: bool = True, storage_available: bool = False) -> dict[str, object]:
    storage = (
        {
            'evidence_available': True,
            'capacity': 114.0,
            'used': 13.4,
            'available': 100.6,
            'headroom': 88.2,
        }
        if storage_available
        else {
            'evidence_available': False,
            'capacity': 0,
            'used': 0,
            'available': 0,
            'headroom': 0,
        }
    )
    payload: dict[str, object] = {
        'cluster': {
            'id': 'cluster-staging',
            'name': 'K8s PGN Staging',
            'environment': 'Staging',
            'status': 'active',
        },
        'cluster_info': {
            'total_nodes': 4,
            'ready_nodes': 4,
            'not_ready_nodes': 0,
            'worker_nodes': 3,
            'master_nodes': 1,
        },
        'metrics_source_status': {
            'connected': True,
            'response_time_ms': 405,
            'last_checked_at': datetime(2026, 8, 3, 1, 5, tzinfo=UTC),
        },
        'capacity_summary': {
            'cpu': {
                'evidence_available': True,
                'capacity': 96.0,
                'used': 1.25,
                'available': 94.75,
                'headroom': 98.7,
            },
            'memory': {
                'evidence_available': True,
                'capacity': 256.0,
                'used': 136.96,
                'available': 119.04,
                'headroom': 46.5,
            },
            'pods': {
                'evidence_available': True,
                'capacity': 440,
                'used': 196,
                'available': 244,
                'headroom': 55.5,
            },
            'storage': storage,
        },
        'allocation_summary': {
            'cpu': {
                'title': 'CPU',
                'available': True,
                'unit': 'cores',
                'status': {'label': 'Healthy', 'tone': 'normal'},
                'items': [
                    {'label': 'Allocatable', 'display': '96.0 cores (100%)', 'percent': 100, 'tone': 'normal'},
                    {
                        'label': 'Configured Requests',
                        'display': '42.0 cores (43.8%)',
                        'percent': 43.8,
                        'tone': 'normal',
                    },
                    {'label': 'Configured Limits', 'display': '78.0 cores (81.2%)', 'percent': 81.2, 'tone': 'warning'},
                    {'label': 'Actual Avg Usage', 'display': '1.25 cores (1.3%)', 'percent': 1.3, 'tone': 'normal'},
                    {'label': 'Peak Usage', 'display': '4.8 cores (5.0%)', 'percent': 5.0, 'tone': 'normal'},
                ],
            },
            'memory': {
                'title': 'Memory',
                'available': True,
                'unit': 'GiB',
                'status': {'label': 'Healthy', 'tone': 'normal'},
                'items': [
                    {'label': 'Allocatable', 'display': '256.0 GiB (100%)', 'percent': 100, 'tone': 'normal'},
                    {'label': 'Configured Requests', 'display': '120.0 GiB (46.9%)', 'percent': 46.9, 'tone': 'normal'},
                    {'label': 'Configured Limits', 'display': '230.0 GiB (89.8%)', 'percent': 89.8, 'tone': 'warning'},
                    {'label': 'Actual Avg Usage', 'display': '136.96 GiB (53.5%)', 'percent': 53.5, 'tone': 'normal'},
                    {'label': 'Peak Usage', 'display': '150.0 GiB (58.6%)', 'percent': 58.6, 'tone': 'normal'},
                ],
            },
            'pods': {
                'title': 'Pods',
                'available': True,
                'unit': 'pods',
                'status': {'label': 'Healthy', 'tone': 'normal'},
                'items': [
                    {'label': 'Pod Capacity', 'display': '440 pods (100%)', 'percent': 100, 'tone': 'normal'},
                    {'label': 'Current Pods', 'display': '196 pods (44.5%)', 'percent': 44.5, 'tone': 'normal'},
                    {'label': 'Remaining Pod Slots', 'display': '244 pods (55.5%)', 'percent': 55.5, 'tone': 'normal'},
                ],
            },
        },
        'risk_summary': [
            {
                'resource': 'cpu',
                'headroom': 98.7,
                'evidence_available': True,
                'status': {'label': 'Healthy', 'tone': 'normal'},
            },
            {
                'resource': 'memory',
                'headroom': 46.5,
                'evidence_available': True,
                'status': {'label': 'Healthy', 'tone': 'normal'},
            },
            {
                'resource': 'pods',
                'headroom': 55.5,
                'evidence_available': True,
                'status': {'label': 'Healthy', 'tone': 'normal'},
            },
            {
                'resource': 'storage',
                'headroom': storage.get('headroom'),
                'evidence_available': storage_available,
                'status': {'label': 'Healthy', 'tone': 'normal'}
                if storage_available
                else {'label': 'Unknown', 'tone': 'unknown'},
            },
        ],
        'governance_findings': [
            {
                'label': 'No actionable capacity governance finding detected',
                'severity': 'normal',
                'tone': 'normal',
            }
        ],
        'recommendation_cards': [
            {
                'title': 'Continue Capacity Monitoring',
                'description': 'Continue monitoring worker capacity, allocation, and headroom trends.',
                'priority': 'Info',
                'source': 'capacity',
            }
        ],
        'source_evidence': [
            {
                'source': 'Metrics Source Observation Cache',
                'freshness': '405 ms',
                'last_collected': datetime(2026, 8, 3, 1, 5, tzinfo=UTC),
            },
            {
                'source': 'Kubernetes Cluster Scope',
                'freshness': 'Committed',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Capacity Analysis Evidence',
                'freshness': '24h',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Forecast Evidence',
                'freshness': '90d',
                'last_collected': datetime(2026, 8, 2, 13, 32, tzinfo=UTC),
            },
        ],
    }
    if include_forecast:
        payload['forecast_payload'] = {
            'forecast_horizon': '90d',
            'forecast_method': 'holt_winters',
            'method_label': 'Holt-Winters',
            'generated_at': datetime(2026, 8, 2, 13, 32, tzinfo=UTC),
            'items': [
                {
                    'key': 'cpu',
                    'projected_percent': 1.4,
                    'historical_points': [{'percent': 1.2}, {'percent': 1.3}],
                    'forecast_points': [{'percent': 1.4}],
                },
                {
                    'key': 'memory',
                    'projected_percent': 65.4,
                    'historical_points': [{'percent': 52.0}, {'percent': 53.5}],
                    'forecast_points': [{'percent': 60.0}, {'percent': 65.4}],
                },
                {
                    'key': 'pods',
                    'projected_percent': 55.4,
                    'historical_points': [{'percent': 44.1}, {'percent': 44.5}],
                    'forecast_points': [{'percent': 50.0}, {'percent': 55.4}],
                },
            ],
        }
    return payload


def _environment(project_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(project_root / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )


def _rendered_html(
    *,
    include_forecast: bool = True,
    storage_available: bool = False,
) -> tuple[object, str, Path]:
    document = build_report_document(
        CapacityAnalysisReportStub(),
        _payload(include_forecast=include_forecast, storage_available=storage_available),
    )
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(document=document)
    return document, rendered_html, project_root


def test_capacity_analysis_uses_approved_nine_page_publication() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/capacity_analysis.html'
    assert document.presentation['page_count'] == 9
    assert document.presentation['presentation_version'] == 'v3.0-capacity-analysis-publication'
    contract = document.presentation['layout_contract']
    assert contract['paper'] == 'A4 Portrait'
    assert contract['page_count'] == 9
    assert contract['fixed_page_canvas'] is True
    assert contract['table_policy'] == 'concise-register-plus-reference'
    assert contract['missing_evidence_policy'] == 'explicit-not-available'
    assert contract['cover_header_policy'] == 'symmetric-two-sided'
    assert contract['section_separator_policy'] == 'none'
    assert contract['table_alignment'] == 'left-middle'
    assert contract['methodology_layout'] == 'parallel-registers'
    assert contract['visual_style'] == 'kaori-publication-v3-neutral-evidence-first'
    assert rendered_html.count('<article class="page') == 9


def test_capacity_analysis_renders_missing_storage_as_explicit_unavailable() -> None:
    document, rendered_html, _ = _rendered_html(storage_available=False)

    storage = document.presentation['storage']['resource']
    assert storage['evidence_available'] is False
    assert storage['headroom_display'] == 'Not Available'
    assert 'Do not infer a healthy storage posture.' in rendered_html
    assert '0% used, 100% headroom, or Normal' in rendered_html
    assert '<span>Storage Headroom</span>' in rendered_html
    assert '<strong class="metric-medium">Not Available</strong>' in rendered_html


def test_capacity_analysis_renders_available_storage_without_false_gap() -> None:
    document, rendered_html, _ = _rendered_html(storage_available=True)

    storage = document.presentation['storage']['resource']
    assert storage['evidence_available'] is True
    assert storage['headroom_display'] == '88.2%'
    assert '13.40 GiB' in rendered_html
    assert '114.00 GiB' in rendered_html
    assert 'Storage evidence is available for review.' in rendered_html


def test_capacity_analysis_methodology_tables_are_separate_and_single_line() -> None:
    _, rendered_html, project_root = _rendered_html()
    shared = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text()
    compact = shared.replace(' ', '')

    assert 'class="methodology-grid"' in rendered_html
    assert 'source-register data-source-table compact-register' in rendered_html
    assert 'methodology-register compact-register' in rendered_html
    assert 'Metrics Source Observation Cache' in rendered_html
    assert '03 Aug 2026 01:05 UTC' in rendered_html
    assert 'grid-template-columns:minmax(0,1.08fr)minmax(0,.92fr)' in compact
    assert 'white-space:nowrap' in compact
    assert 'vertical-align:middle' in compact


def test_capacity_analysis_node_participation_uses_svg_for_weasyprint() -> None:
    document, rendered_html, project_root = _rendered_html()
    stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'capacity_analysis.css').read_text()

    assert 'aria-label="Node participation 100 percent"' in rendered_html
    assert '>4 / 4</text>' in document.presentation['scheduling']['nodes']['donut_svg']
    assert 'conic-gradient' not in stylesheet


def test_capacity_analysis_forecast_has_no_svg_font_collision() -> None:
    _, rendered_html, _ = _rendered_html()
    forecast_section = rendered_html.split('Figure 2 - Capacity Projection Outlook', 1)[1].split(
        'Forecast Interpretation', 1
    )[0]

    assert 'class="value"' not in forecast_section
    assert 'font:11px Inter,sans-serif;font-weight:700' in forecast_section
    source = (
        Path(__file__).resolve().parents[2] / 'app' / 'reports' / 'export' / 'html_pdf' / 'capacity' / 'charts.py'
    ).read_text()
    assert 'resolve_vertical_labels' in source
    assert '65.4%' in forecast_section


def test_capacity_analysis_weasyprint_layout_is_exactly_nine_a4_pages() -> None:
    _, rendered_html, project_root = _rendered_html()
    font_config = FontConfiguration()
    rendered_document = HTML(string=rendered_html, base_url=str(project_root)).render(
        stylesheets=[
            CSS(
                filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'capacity_analysis.css'),
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

    assert len(rendered_document.pages) == 9
    for page in rendered_document.pages:
        assert round(float(page.width), 2) == 793.70
        assert round(float(page.height), 2) == 1122.52


def test_capacity_analysis_renders_explicit_forecast_unavailable_state() -> None:
    document, rendered_html, _ = _rendered_html(include_forecast=False)

    assert document.presentation['forecast']['available'] is False
    assert document.presentation['forecast']['metrics'][0]['value'] == 'Not Available'
    assert 'Forecast Evidence Not Available' in rendered_html
    assert rendered_html.count('<article class="page') == 9


def test_capacity_analysis_engine_uses_isolated_stylesheet() -> None:
    project_root = Path(__file__).resolve().parents[2]
    registry = (
        project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'analytics_publication_standard.py'
    ).read_text()
    engine = (project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text()

    assert "'reports/pdf/capacity_analysis.html': 'capacity_analysis.css'" in registry
    assert 'ANALYTICS_TEMPLATE_STYLESHEETS' in engine
    assert 'ANALYTICS_SHARED_STYLESHEET' in engine


def test_capacity_analysis_payload_uses_committed_forecast_snapshot() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / 'app' / 'reports' / 'export' / 'payloads' / 'capacity.py').read_text()

    assert "dataset_key='analytics.forecast'" in source
    assert 'read_snapshot' in source
    assert 'ForecastAnalysisService' not in source
    assert "'Capacity Analysis Evidence'" in source
