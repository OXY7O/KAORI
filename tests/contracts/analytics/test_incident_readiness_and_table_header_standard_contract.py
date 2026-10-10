import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ANALYTICS_TEMPLATES = ROOT / 'app/templates/kubernetes/analytics'
INCIDENT_TEMPLATE = ANALYTICS_TEMPLATES / 'alerts/partials/_incident_readiness.html'


def _read(relative_path: str) -> str:
    return (ANALYTICS_TEMPLATES / relative_path).read_text(encoding='utf-8')


def test_incident_readiness_uses_compact_operational_workspace() -> None:
    content = INCIDENT_TEMPLATE.read_text(encoding='utf-8')

    assert 'Readiness Posture' in content
    assert 'Readiness Score' in content
    assert 'Response Control Readiness' in content
    assert 'Signal Pressure' in content
    assert 'Critical Signals' in content
    assert 'Warning Signals' in content
    assert 'Anomaly Signals' in content
    assert 'Incident Decision' in content
    assert 'Escalation Gate' in content
    assert 'Readiness Checks' in content
    assert 'status_indicator_label(check.status|title' in content
    assert 'xl:grid-cols-6' not in content
    assert '<details' not in content
    assert '<summary' not in content
    assert 'rounded-xl border border-outline-default bg-surface-subtle p-4' not in content


def test_incident_readiness_redesign_uses_committed_control_evidence() -> None:
    content = INCIDENT_TEMPLATE.read_text(encoding='utf-8')
    source = (ROOT / 'app/kubernetes/analytics/alerts/readiness.py').read_text(encoding='utf-8')

    assert 'data-kaori-readiness-layout' in content
    assert 'xl:grid-cols-[minmax(0,1.65fr)_minmax(19rem,1fr)]' in content
    assert 'stroke-dasharray="{{ incident_readiness.score if has_checks else 0 }} 100"' in content
    assert 'Readiness score unavailable' in content
    assert 'class="mt-3 flex flex-col items-center gap-3"' in content
    assert 'class="min-w-0 w-full text-center"' in content
    assert 'mt-3 flex flex-wrap items-center gap-4' not in content
    assert "analysis_surface.snapshot_shell_classes()" in content
    assert "analysis_surface.nested_evidence_card_classes(" in content
    assert "analysis_surface.guidance_card_classes()" in content

    for section in (
        'Readiness Posture', 'Readiness Score', 'Response Control Readiness',
        'Control Evidence Snapshot', 'Signal Pressure', 'Readiness Checks',
        'Incident Decision', 'Escalation Gate', 'Needs Attention',
        'What This Means',
    ):
        assert section in content
    for field in (
        'incident_readiness.score', 'incident_readiness.label',
        'incident_readiness.recommended_action', 'incident_readiness.source_score',
        'incident_readiness.ownership_score', 'incident_readiness.routing_ready',
        'incident_readiness.critical_signals', 'incident_readiness.warning_signals',
        'incident_readiness.anomaly_signals', 'incident_readiness.silence_risk',
        'incident_readiness.inhibition_risk', 'incident_readiness.checks',
        'check.status', 'check.description',
    ):
        assert field in content

    assert 'check_summary.pass_count' in content
    assert 'check_summary.warning_count' in content
    assert 'check_summary.fail_count' in content
    assert "if check.status != 'pass'" in content
    assert 'if has_checks' in content
    assert 'value if has_checks else' in content
    assert "status_indicator_label(check.status|title" in content
    assert 'aria-label="Incident decision and handoff readiness"' in content
    assert 'caption class="sr-only"' in content
    assert 'min-w-[34rem] table-fixed' in content
    assert "fill_classes='h-full rounded-full bg-kaori-primary'" in content
    assert "progress_bar.semantic_bar" not in content
    assert '35% weight' not in content
    assert 'Last 24 hours' not in content
    assert 'Last updated' not in content
    assert 'Refresh' not in content

    assert "'ownership_score': ownership_score" in source
    assert "'source_score': source_score" in source
    assert "'checks': checks" in source
    assert "score -= 15" in source


def test_incident_readiness_attentional_copy_does_not_hide_handoff_gaps() -> None:
    content = INCIDENT_TEMPLATE.read_text(encoding='utf-8')
    assert 'check_summary.fail_count + check_summary.warning_count > 0' in content
    assert 'Address the gaps before incident handoff' in content
    assert 'response-control gaps still require attention' in content
    assert 'Control evidence is unavailable' in content
    assert 'No readiness control gaps are detected in the committed evidence' in content


def test_analytics_table_headers_follow_kaori_title_case_contract() -> None:
    expected_headers = {
        'alerts/partials/_alerts_table.html': ['Alert', 'Severity', 'State', 'Scope &amp; Source', 'Started', 'Action'],
        'alerts/partials/_anomalies_table.html': ['Anomaly', 'Severity', 'Namespace &amp; Pod', 'Signal', 'Action'],
        'components/_ranked_evidence_panel.html': ['Rank', 'Consumer Identity', 'Contribution to Scope', 'Consumption'],
        'top_consumers/partials/_consumer_detail_results.html': [
            'Rank',
            'Consumer Identity',
            'Resource Evidence',
            'Operational Priority',
            'Action',
        ],
        'storage/partials/_filesystem_panel.html': ['Node &amp; Mount Point', 'Capacity', 'Utilization', 'Risk'],
        'workload/partials/_tenant_quota_section.html': [
            'Namespace',
            'Quota Pressure',
            'Runtime Demand',
            'Risk',
            'Action',
        ],
        'workload/partials/_workload_mapping_section.html': [
            'Workload &amp; Namespace',
            'Configuration &amp; Risk',
            'Request Fit',
            'Evidence &amp; QoS',
            'Action',
        ],
    }

    for relative_path, headers in expected_headers.items():
        content = _read(relative_path)
        for header in headers:
            macro_header = header.replace('&amp;', '&')
            assert (
                f'>{header}</div>' in content
                or f'>{header}</p>' in content
                or f"evidence_list.header_cell('{macro_header}'" in content
            )


def test_table_headers_do_not_use_ambiguous_rank_symbol_or_slash_identity() -> None:
    files = [
        'alerts/partials/_anomalies_table.html',
        'alerts/partials/_anomalies_table_row.html',
        'components/_ranked_evidence_panel.html',
        'top_consumers/partials/_consumer_detail_results.html',
    ]
    combined = '\n'.join(_read(path) for path in files)

    assert '>#</div>' not in combined
    assert '>Namespace / Pod<' not in combined


def test_desktop_column_headers_use_consistent_kaori_presentation_classes() -> None:
    for template_path in ANALYTICS_TEMPLATES.rglob('*.html'):
        content = template_path.read_text(encoding='utf-8')
        header_lines = [
            line
            for line in content.splitlines()
            if 'text-content-muted' in line and 'uppercase' in line and '<div' in line
        ]
        for line in header_lines:
            if re.search(r'>\s*[A-Za-z#]', line):
                assert 'font-semibold' in line
                assert 'tracking-' in line


def test_workload_detail_actions_use_dedicated_action_columns() -> None:
    quota = _read('workload/partials/_tenant_quota_section.html')
    mapping = _read('workload/partials/_workload_mapping_section.html')

    for content in (quota, mapping):
        assert "evidence_list.header_cell('Action'" in content
        assert '<span>View Details</span>' in content
        assert 'aria-haspopup="dialog"' in content
        assert 'record_detail_modal.render' in content
        assert 'data-lucide="scan-search"' not in content
        assert 'data-lucide="panel-top-open"' in content
        assert 'data-lucide="chevron-down"' not in content
        assert 'table_ui.action_classes()' in content
        assert 'w-full whitespace-nowrap sm:w-auto' in content
        assert 'class="group flex w-full items-center gap-3 border-t' not in content
