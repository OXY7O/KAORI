from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
ANALYTICS_TEMPLATES = ROOT / 'app/templates/analytics'
INCIDENT_TEMPLATE = ANALYTICS_TEMPLATES / 'alerts/partials/_incident_readiness.html'


def _read(relative_path: str) -> str:
    return (ANALYTICS_TEMPLATES / relative_path).read_text(encoding='utf-8')


def test_incident_readiness_uses_compact_operational_workspace() -> None:
    content = INCIDENT_TEMPLATE.read_text(encoding='utf-8')

    assert 'Readiness Score' in content
    assert 'Critical Signals' in content
    assert 'Warning Signals' in content
    assert 'Anomaly Signals' in content
    assert 'Recommended Action' in content
    assert 'Readiness Checks' in content
    assert 'xl:grid-cols-6' in content
    assert '<details' not in content
    assert '<summary' not in content
    assert 'rounded-xl border border-outline-default bg-surface-subtle p-4' not in content


def test_analytics_table_headers_follow_kaori_title_case_contract() -> None:
    expected_headers = {
        'alerts/partials/_alerts_table.html': [
            'Alert', 'Severity', 'State', 'Scope &amp; Source', 'Started', 'Action'
        ],
        'alerts/partials/_anomalies_table.html': [
            'Anomaly', 'Severity', 'Namespace &amp; Pod', 'Signal', 'Action'
        ],
        'components/_ranked_evidence_panel.html': [
            'Rank', 'Consumer Identity', 'Contribution to Scope', 'Consumption'
        ],
        'top_consumers/partials/_consumer_detail_results.html': [
            'Rank', 'Consumer Identity', 'Resource Evidence', 'Operational Priority', 'Action'
        ],
        'storage/partials/_filesystem_panel.html': [
            'Node &amp; Mount Point', 'Capacity', 'Utilization', 'Risk'
        ],
        'workload/partials/_tenant_quota_section.html': [
            'Namespace', 'Quota Pressure', 'Runtime Demand', 'Risk', 'Action'
        ],
        'workload/partials/_workload_mapping_section.html': [
            'Workload &amp; Namespace', 'Configuration &amp; Risk', 'Request Fit',
            'Evidence &amp; QoS', 'Action'
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
            line for line in content.splitlines()
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
        assert "expanded ? 'Hide Details' : 'View Details'" in content
        assert 'data-lucide="scan-search"' not in content
        assert 'data-lucide="chevron-down"' in content
        assert 'table_ui.action_classes()' in content
        assert 'w-full whitespace-nowrap sm:w-auto' in content
        assert 'class="group flex w-full items-center gap-3 border-t' not in content
