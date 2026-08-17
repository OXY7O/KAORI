from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.builder import build_report_document


@dataclass
class ResourceUtilizationReportStub:
    id: int = 216
    name: str = 'Resource Utilization Publication Validation'
    report_type: str = 'resource_utilization'
    report_domain: str = 'kubernetes'
    source_kind: str = 'kubernetes'
    cluster_id: str | None = 'cluster-staging'
    namespace: str | None = None
    period: str = '30d'
    output_format: str = 'pdf'
    generated_by_display_name_snapshot: str | None = 'Platform Operations'
    generated_by_username_snapshot: str | None = 'platform-ops'

    def sections_as_list(self) -> list[str]:
        return [
            'executive_summary',
            'cpu_utilization',
            'memory_utilization',
            'pod_utilization',
            'node_resource_detail',
            'operational_recommendations',
        ]


def _payload(*, include_forecast: bool = True) -> dict[str, object]:
    payload: dict[str, object] = {
        'cluster': {
            'id': 'cluster-staging',
            'name': 'K8s PGN Staging',
            'environment': 'Staging',
            'status': 'active',
        },
        'metrics_source_status': {
            'connected': True,
            'status': 'query_ready',
            'status_label': 'Query Ready',
            'response_time_ms': 293,
            'last_checked_at': datetime(2026, 8, 2, 15, 10, tzinfo=UTC),
        },
        'summary': {
            'cpu_utilization': 1.0,
            'memory_utilization': 51.0,
            'storage_utilization': 12.0,
            'pod_utilization': 44.0,
            'pod_capacity': 371,
            'pod_count': 196,
        },
        'cluster_info': {
            'total_nodes': 4,
            'ready_nodes': 4,
            'not_ready_nodes': 0,
            'worker_nodes': 3,
            'master_nodes': 1,
        },
        'risk_assessment': {
            'cpu': {'status': 'Normal'},
            'memory': {'status': 'Normal'},
            'storage': {'status': 'Normal'},
            'pods': {'status': 'Normal'},
        },
        'top_cpu_consumers': [
            {
                'namespace': 'monitoring',
                'pod': 'prometheus-prometheus-kube-prometheus-prometheus',
                'value': 0.17,
            },
            {
                'namespace': 'billing-pgnbilling-staging',
                'pod': 'integration-service-575957488f',
                'value': 0.17,
            },
            {
                'namespace': 'kube-system',
                'pod': 'k8s-master-staging-001.pgn.co.id',
                'value': 0.14,
            },
        ],
        'top_memory_consumers': [
            {
                'namespace': 'openebs',
                'pod': 'cstor-disk-thkc-55cf8fb6fb',
                'value': 16.46,
            },
            {
                'namespace': 'openebs',
                'pod': 'cstor-disk-dfgm-7f4dfcd7cd',
                'value': 16.17,
            },
            {
                'namespace': 'openebs',
                'pod': 'cstor-disk-qmnr-66bddf495',
                'value': 15.49,
            },
        ],
        'trends': {
            'cpu': [{'value': value} for value in (0.8, 1.0, 0.9, 1.1, 1.0)],
            'memory': [{'value': value} for value in (46.0, 48.0, 49.0, 50.0, 51.0)],
            'pods': [{'value': value} for value in (40.0, 41.0, 42.0, 43.0, 44.0)],
        },
        'source_evidence': [
            {
                'source': 'Metrics Source Observation Cache',
                'freshness': '293 ms',
                'last_collected': datetime(2026, 8, 2, 15, 10, tzinfo=UTC),
            },
            {
                'source': 'Kubernetes Cluster Scope',
                'freshness': 'Committed',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Utilization Trend Evidence',
                'freshness': 'Last 30 Days',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Forecast Evidence',
                'freshness': '90d',
                'last_collected': datetime(2026, 8, 2, 15, 14, tzinfo=UTC),
            },
        ],
    }
    if include_forecast:
        payload['forecast_payload'] = {
            'forecast_horizon': '90d',
            'forecast_method': 'holt_winters',
            'method_label': 'Holt-Winters',
            'generated_at': datetime(2026, 8, 2, 15, 14, tzinfo=UTC),
            'items': [
                {
                    'key': 'cpu',
                    'signal_quality': 'High',
                    'projected_percent': 2.0,
                    'historical_points': [{'percent': 0.8}, {'percent': 1.0}],
                    'forecast_points': [{'percent': 1.2}, {'percent': 2.0}],
                },
                {
                    'key': 'memory',
                    'signal_quality': 'High',
                    'projected_percent': 74.0,
                    'historical_points': [
                        {'percent': 46.0},
                        {'percent': 48.0},
                        {'percent': 51.0},
                    ],
                    'forecast_points': [
                        {'percent': 60.0},
                        {'percent': 68.0},
                        {'percent': 74.0},
                    ],
                    'warning_eta': {'label': '178 days'},
                },
                {
                    'key': 'pods',
                    'signal_quality': 'High',
                    'projected_percent': 53.0,
                    'historical_points': [
                        {'percent': 40.0},
                        {'percent': 42.0},
                        {'percent': 44.0},
                    ],
                    'forecast_points': [
                        {'percent': 47.0},
                        {'percent': 50.0},
                        {'percent': 53.0},
                    ],
                },
            ],
        }
    return payload


def _environment(project_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(project_root / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )


def _rendered_html(*, include_forecast: bool = True) -> tuple[object, str, Path]:
    document = build_report_document(
        ResourceUtilizationReportStub(),
        _payload(include_forecast=include_forecast),
    )
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(document=document)
    return document, rendered_html, project_root


def test_resource_utilization_uses_approved_nine_page_publication() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/resource_utilization.html'
    assert document.presentation['page_count'] == 9
    assert document.presentation['presentation_version'] == 'v3.0-resource-utilization-publication'
    contract = document.presentation['layout_contract']
    assert contract['paper'] == 'A4 Portrait'
    assert contract['page_count'] == 9
    assert contract['fixed_page_canvas'] is True
    assert contract['table_policy'] == 'concise-register-plus-reference'
    assert contract['cover_header_policy'] == 'symmetric-two-sided'
    assert contract['section_separator_policy'] == 'none'
    assert contract['table_alignment'] == 'left-middle'
    assert contract['methodology_layout'] == 'parallel-registers'
    assert contract['visual_style'] == 'kaori-publication-v3-neutral-evidence-first'
    assert rendered_html.count('<article class="page') == 9


def test_resource_utilization_template_has_no_duplicate_section_copy() -> None:
    _, rendered_html, _ = _rendered_html()

    assert rendered_html.count('The principal operating signal and the decision required.') == 1
    assert rendered_html.count('Interpretation remains separate from the comparison register.') == 1
    assert rendered_html.count('Current posture and planning implication.') == 1
    assert rendered_html.count('Ready nodes participating in current capacity assumptions.') == 1
    assert rendered_html.count('Relative contribution across the top three displayed CPU consumers.') == 1


def test_resource_utilization_methodology_tables_are_separate_and_single_line() -> None:
    _, rendered_html, project_root = _rendered_html()
    shared = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text()
    compact = shared.replace(' ', '')

    assert 'class="methodology-grid"' in rendered_html
    assert 'source-register data-source-table compact-register' in rendered_html
    assert 'methodology-register compact-register' in rendered_html
    assert 'Metrics Source Observation Cache' in rendered_html
    assert '02 Aug 2026 15:14 UTC' in rendered_html
    assert 'grid-template-columns:minmax(0,1.08fr)minmax(0,.92fr)' in compact
    assert 'white-space:nowrap' in compact
    assert 'vertical-align:middle' in compact


def test_resource_utilization_node_participation_uses_svg_for_weasyprint() -> None:
    _, rendered_html, project_root = _rendered_html()
    stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'resource_utilization.css').read_text()

    assert 'aria-label="Node participation 100 percent"' in rendered_html
    assert '<text x="78" y="76"' in rendered_html
    assert 'conic-gradient' not in stylesheet


def test_resource_utilization_weasyprint_layout_is_exactly_nine_a4_pages() -> None:
    _, rendered_html, project_root = _rendered_html()
    font_config = FontConfiguration()
    rendered_document = HTML(string=rendered_html, base_url=str(project_root)).render(
        stylesheets=[
            CSS(
                filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'resource_utilization.css'),
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


def test_resource_utilization_renders_explicit_forecast_unavailable_state() -> None:
    document, rendered_html, _ = _rendered_html(include_forecast=False)

    assert document.presentation['memory']['metrics'][3]['value'] == 'Not Available'
    assert document.presentation['trend']['metrics'][3]['value'] == 'Not Available'
    assert 'Forecast evidence was not available' in rendered_html
    assert rendered_html.count('<article class="page') == 9


def test_resource_utilization_engine_uses_isolated_stylesheet() -> None:
    project_root = Path(__file__).resolve().parents[2]
    registry = (
        project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'analytics_publication_standard.py'
    ).read_text()
    engine = (project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text()

    assert "'reports/pdf/resource_utilization.html': 'resource_utilization.css'" in registry
    assert 'ANALYTICS_TEMPLATE_STYLESHEETS' in engine
    assert 'ANALYTICS_SHARED_STYLESHEET' in engine


def test_resource_utilization_payload_uses_committed_forecast_snapshot() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = (project_root / 'app' / 'reports' / 'export' / 'payloads' / 'utilization.py').read_text()

    assert "dataset_key='analytics.forecast'" in source
    assert 'read_snapshot' in source
    assert 'ForecastAnalysisService' not in source
    assert 'service.get_trends' in source
