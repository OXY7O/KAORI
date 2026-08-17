from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.builder import build_report_document


@dataclass
class StorageAnalysisReportStub:
    id: int = 246
    name: str = 'Storage Analysis Publication Validation'
    report_type: str = 'storage_analysis'
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
            'filesystem_summary',
            'persistent_volume_summary',
            'persistent_volume_claims',
            'storage_risk',
            'operational_recommendations',
        ]


def _payload(
    *,
    filesystem_available: bool = True,
    persistent_available: bool = True,
    include_forecast: bool = True,
) -> dict[str, object]:
    filesystem_rows = (
        [
            {
                'node': 'k8s-worker-staging-001.pgn.co.id',
                'mountpoint': '/var',
                'capacity': '99.88 GiB',
                'used': '66.11 GiB',
                'free': '33.77 GiB',
                'usage_percent': 66.2,
                'evidence_available': True,
                'capacity_bytes': 107_245_436_416,
                'used_bytes': 70_984_458_240,
                'free_bytes': 36_260_978_176,
                'risk': {'label': 'Healthy', 'tone': 'normal'},
            },
            {
                'node': 'k8s-worker-staging-002.pgn.co.id',
                'mountpoint': '/var',
                'capacity': '99.87 GiB',
                'used': '55.28 GiB',
                'free': '44.59 GiB',
                'usage_percent': 55.4,
                'evidence_available': True,
                'capacity_bytes': 107_234_951_680,
                'used_bytes': 59_356_250_112,
                'free_bytes': 47_878_701_568,
                'risk': {'label': 'Healthy', 'tone': 'normal'},
            },
        ]
        if filesystem_available
        else []
    )
    filesystem_summary = (
        {
            'evidence_available': True,
            'capacity': '199.75 GiB',
            'used': '121.39 GiB',
            'free': '78.36 GiB',
            'usage_percent': 60.8,
            'free_percent': 39.2,
            'highest_usage': 66.2,
            'highest_node': 'k8s-worker-staging-001.pgn.co.id',
            'risk': {'label': 'Healthy', 'tone': 'normal'},
        }
        if filesystem_available
        else {
            'evidence_available': False,
            'capacity': 'N/A',
            'used': 'N/A',
            'free': 'N/A',
            'usage_percent': None,
            'free_percent': None,
            'highest_usage': None,
            'highest_node': '-',
            'risk': {'label': 'Unknown', 'tone': 'unknown'},
        }
    )
    pv_rows = (
        [
            {
                'name': 'pvc-01',
                'status': 'Bound',
                'capacity': '20.00 GiB',
                'capacity_bytes': 21_474_836_480,
                'evidence_available': True,
                'storage_class': 'cstor-csi-disk',
                'claim': 'openebs/data-cstor-disk-thkc',
                'reclaim_policy': 'Delete',
                'risk': {'label': 'Healthy', 'tone': 'normal'},
            },
            {
                'name': 'pvc-02',
                'status': 'Released',
                'capacity': '10.00 GiB',
                'capacity_bytes': 10_737_418_240,
                'evidence_available': True,
                'storage_class': 'cstor-csi-disk',
                'claim': '-',
                'reclaim_policy': 'Retain',
                'risk': {'label': 'Watch', 'tone': 'warning'},
            },
        ]
        if persistent_available
        else []
    )
    pvc_rows = (
        [
            {
                'name': 'data-cstor-disk-thkc',
                'namespace': 'openebs',
                'status': 'Bound',
                'storage_class': 'cstor-csi-disk',
                'requested': '20.00 GiB',
                'used': '16.39 GiB',
                'free': '3.61 GiB',
                'requested_bytes': 21_474_836_480,
                'used_bytes': 17_593_827_328,
                'free_bytes': 3_881_009_152,
                'usage_percent': 82.0,
                'evidence_available': True,
                'risk': {'label': 'Watch', 'tone': 'warning'},
            },
        ]
        if persistent_available
        else []
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
        },
        'metrics_source_status': {
            'connected': True,
            'response_time_ms': 405,
            'last_checked_at': datetime(2026, 8, 3, 1, 5, tzinfo=UTC),
        },
        'selected_namespace': 'All Namespaces',
        'selected_time_range': '24h',
        'storage_summary': {
            'node_filesystem': {
                'available_nodes': ['k8s-worker-staging-001.pgn.co.id', 'k8s-worker-staging-002.pgn.co.id'],
                'scope_label': 'All Nodes',
                'summary': filesystem_summary,
                'all_rows': filesystem_rows,
                'rows': filesystem_rows,
            },
            'persistent_storage': {
                'pv': {
                    'evidence_available': persistent_available,
                    'count': 33 if persistent_available else 0,
                    'capacity': '320.00 GiB' if persistent_available else 'N/A',
                    'observed_claim_usage': '16.39 GiB' if persistent_available else 'N/A',
                    'requested_claim_capacity': '20.00 GiB' if persistent_available else 'N/A',
                    'unallocated_provisioned_difference': '300.00 GiB' if persistent_available else 'N/A',
                    'scope_label': 'Cluster',
                },
                'pvc': {
                    'evidence_available': persistent_available,
                    'count': 1 if persistent_available else 0,
                    'requested': '20.00 GiB' if persistent_available else 'N/A',
                    'used': '16.39 GiB' if persistent_available else 'N/A',
                    'free': '3.61 GiB' if persistent_available else 'N/A',
                    'used_percent': 82.0 if persistent_available else None,
                    'free_percent': 18.0 if persistent_available else None,
                    'scope_label': 'All Namespaces',
                },
                'pv_all_rows': pv_rows,
                'pv_rows': pv_rows,
                'pvc_all_rows': pvc_rows,
                'pvc_rows': pvc_rows,
            },
        },
        'recommendation_cards': [
            {
                'title': 'Review PVC Capacity Utilization',
                'description': 'PVC used capacity is 82.0% with 18.0% free. Validate ownership and expansion policy.',
                'priority': 'Warning',
                'source': 'storage_pvc',
                'is_actionable': True,
            },
            {
                'title': 'Review PV Lifecycle Risk Items',
                'description': 'One released PV requires reclaim-policy and claim-binding review.',
                'priority': 'Warning',
                'source': 'storage_pv',
                'is_actionable': True,
            },
        ],
        'source_evidence': [
            {
                'source': 'Metrics Source Observation Cache',
                'freshness': '405 ms',
                'last_collected': datetime(2026, 8, 3, 1, 5, tzinfo=UTC),
            },
            {
                'source': 'Aggregate Storage Capacity',
                'freshness': 'Committed' if filesystem_available else 'Partial',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Kubernetes Storage Inventory',
                'freshness': 'Committed' if persistent_available else 'Partial',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Forecast Evidence',
                'freshness': '90d' if include_forecast else 'Not Available',
                'last_collected': datetime(2026, 8, 2, 13, 32, tzinfo=UTC) if include_forecast else 'Not Available',
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
                    'key': 'storage',
                    'projected_percent': 68.0,
                    'historical_points': [
                        {'percent': 56.0},
                        {'percent': 58.2},
                        {'percent': 60.8},
                    ],
                    'forecast_points': [
                        {'percent': 64.0},
                        {'percent': 68.0},
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


def _rendered_html(
    *,
    filesystem_available: bool = True,
    persistent_available: bool = True,
    include_forecast: bool = True,
) -> tuple[object, str, Path]:
    document = build_report_document(
        StorageAnalysisReportStub(),
        _payload(
            filesystem_available=filesystem_available,
            persistent_available=persistent_available,
            include_forecast=include_forecast,
        ),
    )
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(document=document)
    return document, rendered_html, project_root


def test_storage_analysis_uses_approved_nine_page_publication() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/storage_analysis.html'
    assert document.presentation['page_count'] == 9
    assert document.presentation['presentation_version'] == 'v3.0-storage-analysis-publication'
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


def test_storage_analysis_renders_committed_aggregate_and_normalized_values() -> None:
    document, rendered_html, _ = _rendered_html()

    capacity = document.presentation['capacity']['resource']
    assert capacity['evidence_available'] is True
    assert capacity['used_display'] == '121.39 GiB'
    assert capacity['capacity_display'] == '199.75 GiB'
    assert capacity['available_display'] == '78.36 GiB'
    assert capacity['used_percent_display'] == '60.8%'
    assert capacity['headroom_display'] == '39.2%'
    assert '121.39 GiB' in rendered_html
    assert '199.75 GiB' in rendered_html


def test_storage_analysis_keeps_missing_filesystem_evidence_explicit() -> None:
    document, rendered_html, _ = _rendered_html(filesystem_available=False)

    capacity = document.presentation['capacity']['resource']
    assert capacity['evidence_available'] is False
    assert capacity['used_display'] == 'Not Available'
    assert capacity['headroom_display'] == 'Not Available'
    assert 'Aggregate capacity evidence is not available.' in rendered_html
    assert 'must not become zero or Normal' in rendered_html


def test_storage_analysis_keeps_inventory_and_utilization_boundaries_separate() -> None:
    document, rendered_html, _ = _rendered_html(persistent_available=False)

    persistent = document.presentation['persistent']
    assert persistent['pv']['count_display'] == 'Not Available'
    assert persistent['pvc']['used_percent_display'] == 'Not Available'
    assert 'Inventory does not equal utilization.' in rendered_html
    assert 'No committed PVC utilization rows are available.' in rendered_html


def test_storage_analysis_does_not_synthesize_missing_trend() -> None:
    document, rendered_html, _ = _rendered_html(include_forecast=False)

    assert document.presentation['trend']['available'] is False
    assert document.presentation['trend']['chart_svg'] == ''
    assert 'Committed storage trend evidence is not available.' in rendered_html
    assert 'no historical or forecast line is synthesized' in rendered_html


def test_storage_analysis_methodology_tables_remain_separate_and_single_line() -> None:
    _, rendered_html, project_root = _rendered_html()
    shared = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text()
    compact = shared.replace(' ', '')

    assert 'class="methodology-grid"' in rendered_html
    assert 'source-register data-source-table compact-register' in rendered_html
    assert 'methodology-register compact-register' in rendered_html
    assert 'Data Sources and Coverage' in rendered_html
    assert 'Methodology Register' in rendered_html
    assert 'grid-template-columns:minmax(0,1.08fr)minmax(0,.92fr)' in compact
    assert 'white-space:nowrap' in compact


def test_storage_analysis_weasyprint_layout_is_exactly_nine_a4_pages(tmp_path: Path) -> None:
    document, rendered_html, project_root = _rendered_html()
    font_config = FontConfiguration()
    stylesheet = project_root / 'app' / 'static' / 'reports' / 'pdf' / 'storage_analysis.css'
    shared_stylesheet = project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css'
    output = tmp_path / 'storage-analysis.pdf'

    rendered = HTML(string=rendered_html, base_url=str(project_root)).render(
        stylesheets=[
            CSS(filename=str(stylesheet), font_config=font_config),
            CSS(filename=str(shared_stylesheet), font_config=font_config),
        ],
        font_config=font_config,
        presentational_hints=True,
    )
    rendered.write_pdf(output)

    assert len(rendered.pages) == 9
    assert output.exists()
    assert output.stat().st_size > 1000
    assert document.presentation['page_count'] == 9


def test_storage_analysis_stylesheet_is_isolated_from_generic_report_css() -> None:
    project_root = Path(__file__).resolve().parents[2]
    registry = (
        project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'analytics_publication_standard.py'
    ).read_text()
    engine = (project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text()

    assert "'reports/pdf/storage_analysis.html': 'storage_analysis.css'" in registry
    assert 'ANALYTICS_TEMPLATE_STYLESHEETS' in engine
