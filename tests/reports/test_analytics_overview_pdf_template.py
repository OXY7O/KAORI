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
    name: str = 'Analytics Overview Reporting Standard V2.6 Validation'
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
            'pvc_capacity': '8.0 TB',
            'pvc_used': '6.4 TB',
            'pvc_risk_count': 2,
            'used_percent': 80.0,
            'free_percent': 20.0,
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
    rendered_html = _environment(project_root).get_template(document.template_name).render(document=document)
    return document, rendered_html, project_root


def test_analytics_overview_uses_reporting_standard_v29_and_12_pages() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/analytics_overview.html'
    assert document.metadata['selected_section_keys'] == list(ANALYTICS_OVERVIEW_SECTION_KEYS)
    assert document.presentation['page_count'] == 12
    assert document.presentation['presentation_version'] == 'v3.0-analytics-overview-publication'
    contract = document.presentation['layout_contract']
    assert contract['paper'] == 'A4 Portrait'
    assert contract['page_count'] == 12
    assert contract['fixed_page_canvas'] is True
    assert contract['section_page_breaks'] is True
    assert contract['truncate_identities'] is False
    assert contract['identity_policy'] == 'reference-register'
    assert contract['status_style'] == 'plain-colored-text'
    assert contract['cover_header_policy'] == 'symmetric-two-sided'
    assert contract['section_separator_policy'] == 'none'
    assert contract['table_alignment'] == 'left-middle'
    assert contract['methodology_layout'] == 'parallel-registers'
    assert contract['visual_style'] == 'kaori-publication-v3-neutral-evidence-first'
    assert rendered_html.count('<article class="page') == 12


def test_analytics_overview_uses_management_summary_and_overview_limits() -> None:
    document, rendered_html, _ = _rendered_html()

    summary = document.presentation['executive']['management_summary']
    assert 'highest available shared-resource signal' in summary
    assert 'local storage risk item' in summary
    assert 'What Management Should Know' in rendered_html
    assert 'Concise decisions stay in-table; full context remains by reference.' in rendered_html
    assert 'Stable reference codes map to the full technical identities shown below.' in rendered_html


def test_analytics_overview_title_case_and_section_title_contract() -> None:
    _, rendered_html, _ = _rendered_html()

    for heading in (
        'What Management Should Know',
        'Figure 1 - Memory Demand Forecast',
        'Figure 2 - Leading Consumer Signals',
        'Figure 3 - Alert Profile',
        'Figure 4 - Report Status Distribution',
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
            CSS(
                filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css'),
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
    payload['metrics_source'] = {
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
    assert memory_metric['value'] == '61.2%'


def test_analytics_overview_css_locks_page_footer_and_table_overflow() -> None:
    _, _, project_root = _rendered_html()
    shared_stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text()
    specialization = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css').read_text()
    compact = shared_stylesheet.replace(' ', '')

    assert '@page' in shared_stylesheet
    assert 'height:297mm' in compact
    assert 'page-break-after:always' in compact
    assert 'width:210mm' in compact
    assert '.report-header' in shared_stylesheet
    assert 'bottom:4.2mm' in compact
    assert 'overflow-wrap:anywhere' in compact
    assert 'table-layout:fixed' in compact
    assert 'vertical-align:middle' in compact
    assert 'text-overflow:ellipsis' not in compact
    assert '@page' not in specialization


def test_v27_layout_uses_distinct_cover_and_reference_components() -> None:
    _, rendered_html, _ = _rendered_html()

    assert 'class="page cover"' in rendered_html
    assert 'class="cover-band"' in rendered_html
    assert 'class="report-header"' in rendered_html
    assert 'Priority Findings and Decisions' in rendered_html
    assert 'Complete Consumer Identities' in rendered_html
    assert 'Data Reliability Guidance' in rendered_html
    assert 'Methodology &amp; Evidence Boundary' in rendered_html
    assert 'Finding References' in rendered_html
    assert 'Capacity References' in rendered_html
    assert 'Forecast References' in rendered_html
    assert 'Risk References' in rendered_html
    assert 'Recommendation References' in rendered_html
    assert 'Methodology Register' in rendered_html
    assert 'Methodology References' in rendered_html
    assert 'Status Language' in rendered_html


def test_v27_css_has_locked_canvas_and_reference_rhythm() -> None:
    _, _, project_root = _rendered_html()
    shared_stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text()
    specialization = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css').read_text()
    compact = shared_stylesheet.replace(' ', '')

    assert '.cover-band' in shared_stylesheet
    assert '.page-title-row' in shared_stylesheet
    assert '.section-body' in shared_stylesheet
    assert '.reference-notes' in shared_stylesheet
    assert '.reference-item' in shared_stylesheet
    assert 'inset:0' not in compact
    assert 'width:210mm' in compact
    assert '.consumer-chart' in specialization
    assert '.page-methodology' in specialization
    assert '.page-methodology' in specialization


def test_analytics_engine_isolates_approved_stylesheet() -> None:
    project_root = Path(__file__).resolve().parents[2]
    registry = (
        project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'analytics_publication_standard.py'
    ).read_text(encoding='utf-8')
    engine = (project_root / 'app' / 'reports' / 'export' / 'html_pdf' / 'engine.py').read_text(encoding='utf-8')

    assert "'reports/pdf/analytics_overview.html': 'analytics_overview.css'" in registry
    assert 'analytics_css_path = css_path.with_name(ANALYTICS_SHARED_STYLESHEET)' in engine
    assert 'CSS(filename=str(report_css_path)' in engine
    assert 'CSS(filename=str(analytics_css_path)' in engine
    assert engine.index('CSS(filename=str(report_css_path)') < engine.index('CSS(filename=str(analytics_css_path)')


def test_v27_template_uses_approved_content_budgets() -> None:
    _, rendered_html, project_root = _rendered_html()
    template_source = (project_root / 'app' / 'templates' / 'reports' / 'pdf' / 'analytics_overview.html').read_text()

    assert rendered_html.count('<article class="page') == 12
    assert 'p.alerts.alerts[:3]' in template_source
    assert 'p.alerts.anomalies[:2]' in template_source
    assert 'Observations by Recency' not in template_source
    assert 'Data Sources and Methodology' in rendered_html
    assert 'Limitations and Status Language' in rendered_html


def test_v27_table_reference_contract_keeps_description_out_of_registers() -> None:
    document, rendered_html, project_root = _rendered_html()
    template_source = (project_root / 'app' / 'templates' / 'reports' / 'pdf' / 'analytics_overview.html').read_text()

    primary = document.presentation['recommendations']['primary']
    assert primary['description']
    assert primary['recommended_action']
    assert 'register_title' in document.presentation['recommendations']['items'][0]
    assert 'recommendation-register' in template_source
    assert 'recommendation-references' in template_source
    register = template_source.split('recommendation-register', 1)[1].split('</table>', 1)[0]
    recommendation_header = '<th>Recommendation</th>'
    owner_header = '<th>Owner</th>'
    assert recommendation_header in register
    assert owner_header in register
    assert register.index(recommendation_header) < register.index(owner_header)
    assert '<th>Interpretation</th>' not in template_source
    assert 'Status Register' not in rendered_html
    assert 'status-legend-grid' not in template_source
    assert 'ui.status_language(p.methodology.status_language)' in template_source
    assert 'class="axis-warning"' in rendered_html
    assert 'class="axis-critical"' in rendered_html


def test_v27_register_titles_are_compact_but_reference_titles_remain_complete() -> None:
    document, rendered_html, _ = _rendered_html()
    item = document.presentation['recommendations']['items'][0]

    assert item['title'] == 'Expand low-headroom persistent volumes with long names'
    assert item['register_title'] == 'Expand low-headroom persistent volumes with...'
    assert item['title'] in rendered_html
    assert item['register_title'] in rendered_html


def test_v27_alert_profile_uses_donut_and_methodology_values_do_not_break_mid_phrase() -> None:
    document, rendered_html, project_root = _rendered_html()
    stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css').read_text()

    assert 'ao-alert-donut' in document.presentation['alerts']['severity_svg']
    assert 'donut-total' in document.presentation['alerts']['severity_svg']
    assert 'Alert severity distribution' in document.presentation['alerts']['severity_svg']
    assert 'class="page page-alerts"' in rendered_html
    assert 'class="freshness-value"' in rendered_html
    assert 'class="freshness-value"' in rendered_html
    assert 'white-space: nowrap' in stylesheet


def test_analytics_overview_v29_precision_layout_contract() -> None:
    document, rendered_html, project_root = _rendered_html()
    shared_stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text(
        encoding='utf-8'
    )
    specialization = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css').read_text(
        encoding='utf-8'
    )
    shared_compact = shared_stylesheet.replace(' ', '').replace('\n', '')

    assert document.presentation['presentation_version'] == 'v3.0-analytics-overview-publication'
    contract = document.presentation['layout_contract']
    assert contract['visual_style'] == 'kaori-publication-v3-neutral-evidence-first'
    assert contract['cover_header_policy'] == 'symmetric-two-sided'
    assert contract['section_separator_policy'] == 'none'
    assert contract['section_rhythm'] == 'title-subtitle-content'
    assert contract['table_alignment'] == 'left-middle'
    assert contract['methodology_layout'] == 'parallel-registers'

    assert '.cover-masthead' in shared_stylesheet
    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)' in shared_stylesheet
    assert '.section-rule' in shared_stylesheet and 'display: none' in shared_stylesheet
    assert 'vertical-align: middle' in shared_stylesheet
    assert '.methodology-grid' in shared_stylesheet
    assert '.limitations-grid' in shared_stylesheet
    assert '.status-language-grid' in shared_stylesheet
    assert '.cover-contents' in shared_stylesheet
    assert '.content-section' in shared_stylesheet
    assert 'display:grid' in shared_compact

    assert '.consumer-group' in specialization
    assert '.page-alerts .content-section' not in specialization
    assert '.page-reporting .content-section' not in specialization
    assert '.methodology-register-layout' in specialization

    assert rendered_html.count('class="consumer-group"') == 2
    assert 'class="method-row"' in rendered_html
    assert 'class="method-rule"' in rendered_html
    assert 'class="method-setting"' in rendered_html
    assert 'donut-caption-below' in document.presentation['alerts']['severity_svg']


def test_analytics_overview_separates_node_filesystem_and_pvc_capacity_evidence() -> None:
    document, rendered_html, _ = _rendered_html()
    presentation = document.presentation

    assert presentation['resource_posture']['shared_rows'][2]['label'] == 'Node Filesystem'
    storage_row = presentation['resource_posture']['capacity_rows'][0]
    assert storage_row['resource'] == 'PVC Storage'
    assert storage_row['capacity'] == '8.0 TB'
    assert storage_row['headroom'] == '20.0%'
    assert presentation['executive']['metrics'][2]['label'] == 'PVC Headroom'
    assert 'PVC, Pod, and Node Capacity' in rendered_html


def test_analytics_overview_forecast_row_uses_same_series_for_current_and_projection() -> None:
    payload = _payload()
    payload['forecast_snapshot'] = {
        'series': [
            {
                'key': 'storage',
                'label': 'PVC Storage',
                'historical_points': '0,87.5 50,85.0',
                'forecast_points': '50,85.0 100,82.0',
                'latest_percent': 15.0,
                'projected_percent': 18.0,
                'confidence': 'Stable History',
                'trend': 'Increasing',
            },
            {
                'key': 'memory',
                'label': 'Memory',
                'historical_points': '0,45 50,39',
                'forecast_points': '50,39 100,27',
                'latest_percent': 61.0,
                'projected_percent': 73.0,
                'confidence': 'Stable History',
                'trend': 'Increasing',
            },
        ],
        'nearest_warning': {'resource': 'memory', 'label': '90 Days'},
        'highest_projected_resource': 'Memory',
        'highest_projected_percent': 73.0,
    }

    document = build_report_document(AnalyticsOverviewReportStub(), payload)
    rows = {row['resource']: row for row in document.presentation['trend_forecast']['resource_rows']}

    assert rows['PVC Storage']['current'] == '15.0%'
    assert rows['PVC Storage']['projected'] == '18.0%'
    assert rows['PVC Storage']['confidence'] == 'Stable History'
    assert rows['Memory']['current'] == '61.0%'
    assert rows['Memory']['projected'] == '73.0%'
    assert rows['Memory']['eta'] == '90 Days'


def test_analytics_overview_fixed_registers_use_publication_safe_one_line_fields() -> None:
    _, rendered_html, project_root = _rendered_html()
    template = (project_root / 'app' / 'templates' / 'reports' / 'pdf' / 'analytics_overview.html').read_text()
    stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css').read_text()

    assert '<th>Threshold ETA</th>' in template
    assert 'row.eta|default' in template
    assert 'consumer-identities' in template
    assert '.forecast-register th:nth-child(6)' in stylesheet
    assert '.forecast-register td { white-space: nowrap; }' in stylesheet
    assert '.page-consumers .identity-title { white-space: nowrap; }' in stylesheet


def test_analytics_overview_pdf_standard_documents_precision_semantics() -> None:
    project_root = Path(__file__).resolve().parents[2]
    standard = (project_root / 'docs' / 'reports' / 'kaori-analytics-pdf-publication-standard-v3.md').read_text()

    assert 'Precision-layout refinement (2026-08-21)' in standard
    assert 'same evidence series and denominator' in standard
    assert 'Raw ISO timestamps with microseconds are prohibited' in standard
    assert 'Node-filesystem utilization' in standard


def test_analytics_overview_prioritizes_p1_before_p2_and_p3_in_management_registers() -> None:
    payload = _payload()
    payload['actionable_recommendations'] = {
        'items': [
            {'title': 'Low Priority', 'description': 'Later review.', 'priority': 'Info', 'source': 'Analytics'},
            {
                'title': 'Urgent Workload Governance',
                'description': 'Immediate review.',
                'priority': 'Critical',
                'source': 'Workload Analysis',
            },
            {
                'title': 'Capacity Review',
                'description': 'Review headroom.',
                'priority': 'Warning',
                'source': 'Capacity Analysis',
            },
        ]
    }

    document = build_report_document(AnalyticsOverviewReportStub(), payload)
    recommendation_items = document.presentation['recommendations']['items']
    executive_findings = document.presentation['executive']['findings']

    assert [item['priority'] for item in recommendation_items[:3]] == ['P1', 'P2', 'P3']
    assert executive_findings[0]['title'] == 'Urgent Workload Governance'


def test_analytics_overview_r2_management_typography_and_helper_copy_contract() -> None:
    _, rendered_html, project_root = _rendered_html()
    stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_overview.css').read_text()

    for helper in (
        'Detailed management references explain the findings summarized above.',
        'Reference notes explain the comparison outcome for each shared resource.',
        'Reference notes explain each projected signal and its operating interpretation.',
        'Stable reference codes map to the full technical identities shown below.',
        'Current use, capacity baseline, and remaining headroom.',
        'Reference notes describe the operational focus behind each highlighted risk item.',
        'Stable reference codes preserve complete alert identities without overloading the comparison table.',
        'Active schedules for the selected reporting boundary are listed below.',
        'Latest generated outputs and their current status.',
        'Reporting posture and artifact-storage readiness.',
        'Cluster inventory counts for the selected reporting boundary.',
        'Node readiness comes from the committed inventory snapshot.',
        'Source freshness, lag, and availability by dataset.',
        'Open data-quality issues affecting completeness or interpretation.',
        'Ownership, validation, and execution controls for the current actions.',
        'Source boundaries and interpretation rules for this report.',
        'Operational limits and standardized status definitions.',
    ):
        assert helper in rendered_html

    shared_stylesheet = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css').read_text()

    assert '--analytics-type-body: 8pt' in shared_stylesheet
    assert '--analytics-type-section: 10.2pt' in shared_stylesheet
    assert '--analytics-type-page: 14.6pt' in shared_stylesheet
    assert '--analytics-rhythm-section: 5.6mm' in shared_stylesheet
    assert '.report-use-advisory' in stylesheet
    assert 'max-width: 100%' in stylesheet


def test_analytics_overview_r2_freshness_register_uses_short_publication_labels() -> None:
    document, rendered_html, _ = _rendered_html()
    rows = document.presentation['freshness']['sources']

    assert rows[0]['source_short'] == 'Metrics Cache'
    assert rows[1]['source_short'] == 'Kubernetes Inventory'
    assert rows[2]['source_short'] == 'Analytics Snapshots'
    assert rows[3]['source_short'] == 'Alert Cache'
    assert rows[1]['status_short'] == 'Current'
    assert 'Metrics Source Observation Cache</td>' not in rendered_html
    assert 'Alertmanager Observation Cache</td>' not in rendered_html


def test_analytics_overview_r2_methodology_guidance_is_full_width_advisory() -> None:
    _, rendered_html, _ = _rendered_html()

    assert 'class="report-use-advisory"' in rendered_html
    assert rendered_html.index('class="status-language-block"') < rendered_html.index('class="report-use-advisory"')
    assert '<strong>Operational Use</strong>' in rendered_html
