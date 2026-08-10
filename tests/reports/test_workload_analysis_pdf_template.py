from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.builder import build_report_document


@dataclass
class WorkloadAnalysisReportStub:
    id: int = 381
    name: str = 'Workload Analysis Publication Validation'
    report_type: str = 'workload_analysis'
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
            'tenant_quota_summary',
            'request_limit_coverage',
            'workload_resource_mapping',
            'governance_findings',
            'operational_recommendations',
        ]


def _payload(*, quota_available: bool = True, mapping_available: bool = True) -> dict[str, object]:
    quota_rows = (
        [
            {
                'namespace': 'billing-pgnbilling-staging',
                'quota_status': {'label': 'Complete'},
                'quota_pressure_available': True,
                'quota_usage_percent': 62.0,
                'risk': {'label': 'Low'},
            },
            {
                'namespace': 'pgnmobile-staging',
                'quota_status': {'label': 'Partial'},
                'quota_pressure_available': True,
                'quota_usage_percent': 81.0,
                'risk': {'label': 'Medium'},
            },
            {
                'namespace': 'url-shortener-staging',
                'quota_status': {'label': 'Missing'},
                'quota_pressure_available': False,
                'quota_usage_percent': 0,
                'risk': {'label': 'High'},
            },
        ]
        if quota_available
        else []
    )
    mapping_rows = (
        [
            {
                'workload': 'integration-service',
                'type': 'Deployment',
                'namespace': 'billing-pgnbilling-staging',
                'replicas': 3,
                'request_coverage': {'label': 'Complete'},
                'limit_coverage': {'label': 'Complete'},
                'metrics_coverage': {'label': 'Complete'},
                'qos': {'label': 'Burstable'},
                'risk': {'label': 'Low'},
                'recommendation': 'Continue monitoring.',
            },
            {
                'workload': 'mobile-api',
                'type': 'Deployment',
                'namespace': 'pgnmobile-staging',
                'replicas': 4,
                'request_coverage': {'label': 'Partial'},
                'limit_coverage': {'label': 'Memory Limit Missing'},
                'metrics_coverage': {'label': 'Partial'},
                'qos': {'label': 'Burstable'},
                'risk': {'label': 'Medium'},
                'recommendation': 'Increase memory request after validation.',
            },
            {
                'workload': 'url-shortener',
                'type': 'Deployment',
                'namespace': 'url-shortener-staging',
                'replicas': 2,
                'request_coverage': {'label': 'Missing'},
                'limit_coverage': {'label': 'Limits Unset'},
                'metrics_coverage': {'label': 'Partial'},
                'qos': {'label': 'BestEffort'},
                'risk': {'label': 'High'},
                'recommendation': 'Set requests and limits.',
            },
        ]
        if mapping_available
        else []
    )
    return {
        'cluster': {
            'id': 'cluster-staging',
            'name': 'K8s PGN Staging',
            'environment': 'Staging',
            'status': 'active',
        },
        'namespace_options': [
            'billing-pgnbilling-staging',
            'pgnmobile-staging',
            'url-shortener-staging',
        ],
        'prometheus_status': {'connected': True, 'response_time_ms': 390},
        'tenant_quota_summary': {
            'scope_total': len(quota_rows),
            'scope_covered': sum(
                1 for item in quota_rows if item.get('quota_status', {}).get('label') in {'Complete', 'Partial'}
            ),
            'scope_near_limit_count': 1 if quota_rows else 0,
            'rows': quota_rows,
        },
        'tenant_quota_rows': quota_rows,
        'workload_mapping_payload': {'rows': mapping_rows},
        'workload_mapping_rows': mapping_rows,
        'governance_findings': [
            {
                'label': '1 Namespace Without ResourceQuota',
                'severity': 'warning',
                'filter': 'missing-quota',
            },
            {
                'label': '2 Workloads With Incomplete Requests',
                'severity': 'critical',
                'filter': 'missing-request',
            },
            {
                'label': '1 BestEffort Workload',
                'severity': 'warning',
                'filter': 'best-effort',
            },
        ],
        'actionable_recommendations': [
            {
                'title': 'Create Missing Namespace ResourceQuota',
                'description': 'Define CPU, memory, and pod boundaries for the namespace.',
                'priority': 'Critical',
                'is_actionable': True,
            },
            {
                'title': 'Review BestEffort Workload Configuration',
                'description': 'Set CPU and memory requests after validating application behavior.',
                'priority': 'Warning',
                'is_actionable': True,
            },
        ],
        'source_evidence': [
            {
                'source': 'Prometheus Workload Evidence',
                'freshness': '390 ms',
                'last_collected': '03 Aug 2026 03:35 UTC',
            },
            {
                'source': 'Tenant Quota Analysis',
                'freshness': 'Committed' if quota_rows else 'Not Available',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Workload Resource Mapping',
                'freshness': 'Committed' if mapping_rows else 'Not Available',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Governance Recommendation Evidence',
                'freshness': 'Committed',
                'last_collected': 'At report cut-off',
            },
        ],
    }


def _environment(project_root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(project_root / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )


def _rendered_html(
    *,
    quota_available: bool = True,
    mapping_available: bool = True,
) -> tuple[object, str, Path]:
    document = build_report_document(
        WorkloadAnalysisReportStub(),
        _payload(quota_available=quota_available, mapping_available=mapping_available),
    )
    project_root = Path(__file__).resolve().parents[2]
    rendered_html = _environment(project_root).get_template(document.template_name).render(document=document)
    return document, rendered_html, project_root


def test_workload_analysis_uses_approved_nine_page_publication() -> None:
    document, rendered_html, _ = _rendered_html()

    assert document.template_name == 'reports/pdf/workload_analysis.html'
    assert document.presentation['page_count'] == 9
    assert document.presentation['presentation_version'] == 'v3.0-workload-analysis-publication'
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


def test_workload_analysis_derives_inventory_from_committed_mapping_rows() -> None:
    document, rendered_html, _ = _rendered_html()

    inventory = document.presentation['inventory']['summary']
    assert inventory['workload_count'] == 3
    assert inventory['pod_count'] == 9
    assert inventory['namespace_count'] == 3
    assert inventory['coverage_display'] == '100%'
    assert '3 workload(s)' in document.presentation['executive']['interpretation_body']
    assert 'Inventory and Runtime Register' in rendered_html


def test_workload_analysis_keeps_missing_quota_evidence_explicit() -> None:
    document, rendered_html, _ = _rendered_html(quota_available=False)

    quota = document.presentation['quota']
    assert quota['available'] is False
    assert quota['coverage_display'] == 'Not Available'
    assert quota['status'] == 'Not Available'
    assert 'Quota posture cannot be assigned.' in rendered_html
    assert 'No committed tenant quota rows are available.' in rendered_html


def test_workload_analysis_does_not_infer_application_owner_mapping() -> None:
    document, rendered_html, _ = _rendered_html()

    owner_metric = document.presentation['mapping']['metrics'][3]
    assert owner_metric == {
        'label': 'Owner Mapping',
        'value': 'Not Available',
        'status': 'Not Committed',
        'tone': 'warning',
    }
    assert 'Application Owner' in rendered_html
    assert 'Not Committed' in rendered_html


def test_workload_analysis_inventory_management_decision_has_overlap_guard() -> None:
    _, rendered_html, project_root = _rendered_html()
    css = (project_root / 'app' / 'static' / 'reports' / 'pdf' / 'workload_analysis.css').read_text()

    assert 'class="content-section management-decision"' in rendered_html
    assert '.page-workload-inventory .management-decision { margin-top: 7mm; }' in css
    assert rendered_html.index('Inventory and Runtime Register') < rendered_html.index('Management Decision')


def test_workload_analysis_weasyprint_layout_is_exactly_nine_a4_pages() -> None:
    _, rendered_html, project_root = _rendered_html()
    font_config = FontConfiguration()
    stylesheet = CSS(
        filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'workload_analysis.css'),
        font_config=font_config,
    )
    shared_stylesheet = CSS(
        filename=str(project_root / 'app' / 'static' / 'reports' / 'pdf' / 'analytics_publication.css'),
        font_config=font_config,
    )

    rendered = HTML(string=rendered_html, base_url=str(project_root)).render(
        stylesheets=[stylesheet, shared_stylesheet],
        font_config=font_config,
        presentational_hints=True,
    )

    assert len(rendered.pages) == 9
    for page in rendered.pages:
        assert round(float(page.width), 2) == 793.70
        assert round(float(page.height), 2) == 1122.52
