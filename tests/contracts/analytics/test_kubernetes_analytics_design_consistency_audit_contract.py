import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ANALYTICS_TEMPLATES = ROOT / 'app/templates/analytics/kubernetes'


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def all_analytics_templates() -> str:
    return '\n'.join(path.read_text(encoding='utf-8') for path in ANALYTICS_TEMPLATES.rglob('*.html'))


def test_shared_controls_and_metrics_source_contract_are_compatible() -> None:
    workspace = read('app/templates/analytics/kubernetes/components/_analysis_workspace.html')
    metrics_source = read('app/templates/analytics/kubernetes/components/_metrics_source_status.html')

    assert 'data-analytics-metrics-source-status' in metrics_source
    assert 'Metrics Source Status' in metrics_source
    assert 'Query Ready' in metrics_source
    assert 'Query Degraded' in metrics_source
    assert 'Response' in metrics_source
    assert 'Checked At' in metrics_source
    assert 'materialization' not in metrics_source
    assert 'metrics_source_status_panel.render(status)' in workspace
    assert 'Latest Data Snapshot' in workspace
    assert 'Source Evidence Incomplete' in workspace
    assert 'Latest Refresh Error' in workspace
    assert 'loading_bar.render(indicator_id' in workspace


def test_analytics_tabs_use_one_shared_runtime_and_native_fallback() -> None:
    tabs = read('app/templates/components/content_tabs.html')
    runtime = read('app/static/js/analytics/controls.js')

    assert 'render_buttons' in tabs
    assert 'nowrap=false' in tabs
    assert 'min-w-max flex-nowrap' in tabs
    assert 'stabilizeAnalyticsTabsets' in runtime
    assert 'setAnalyticsTab' in runtime
    assert 'kaoriAnalyticsTabs' not in runtime
    assert 'const alpineState = tabset._x_dataStack' not in runtime
    assert 'const alpineTab = tabset._x_dataStack' not in runtime
    assert 'candidate.isConnected' in runtime
    assert 'stabilizeTopConsumersAfterSwap' not in runtime

    for template in (
        'app/templates/analytics/kubernetes/overview/index.html',
        'app/templates/analytics/kubernetes/alerts/index.html',
        'app/templates/analytics/kubernetes/top_consumers/partials/_top_consumers_section.html',
        'app/templates/analytics/kubernetes/utilization/index.html',
        'app/templates/analytics/kubernetes/capacity/index.html',
        'app/templates/analytics/kubernetes/storage/partials/_storage_section.html',
        'app/templates/analytics/kubernetes/workload/index.html',
        'app/templates/analytics/kubernetes/forecast/partials/_forecast_section.html',
    ):
        content = read(template)
        assert 'data-analytics-tabset' in content or 'analytics_workspace.tabbed' in content


def test_analytics_templates_do_not_use_nonstandard_layout_patterns() -> None:
    content = all_analytics_templates()

    for forbidden in (
        '<details',
        '<summary',
        'overflow-x-auto',
        'style=',
        'bg-red-',
        'text-red-',
        'border-red-',
        'bg-amber-',
        'text-amber-',
        'border-amber-',
        'bg-green-',
        'text-green-',
        'border-green-',
        'bg-blue-',
        'text-blue-',
        'border-blue-',
        'bg-cyan-',
        'text-cyan-',
        'border-cyan-',
    ):
        assert forbidden not in content


def test_analytics_filter_forms_have_loading_and_request_synchronization() -> None:
    for path in ANALYTICS_TEMPLATES.rglob('*.html'):
        content = path.read_text(encoding='utf-8')
        for match in re.finditer(r'<form\b[^>]*>', content, re.DOTALL):
            tag = match.group(0)
            if 'hx-get=' not in tag:
                continue
            assert 'hx-indicator=' in tag, f'Missing hx-indicator in {path}'
            assert 'hx-sync=' in tag, f'Missing hx-sync in {path}'


def test_large_analytics_record_sections_use_responsive_rows() -> None:
    anomaly = read('app/templates/analytics/kubernetes/alerts/partials/_anomalies_table.html')
    filesystem = read('app/templates/analytics/kubernetes/storage/partials/_filesystem_panel.html')
    pvc = read('app/templates/analytics/kubernetes/storage/partials/_persistent_volume_claims_panel.html')
    pv = read('app/templates/analytics/kubernetes/storage/partials/_persistent_volumes_panel.html')
    quota = read('app/templates/analytics/kubernetes/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/kubernetes/workload/partials/_workload_mapping_section.html')

    for content in (anomaly, filesystem, pvc, pv, quota, mapping):
        assert 'overflow-x-auto' not in content
    assert 'Anomaly Candidates' in anomaly
    assert 'Node Filesystem Usage' in filesystem
    assert 'Persistent Volume Claims' in pvc
    assert 'Persistent Volumes' in pv
    assert 'Tenant Quota Analysis' in quota
    assert 'Workload Resource Mapping' in mapping


def test_shared_status_notice_and_safe_materialization_pending_label() -> None:
    notice = read('app/templates/analytics/kubernetes/components/_status_notice.html')
    pending = read('app/templates/analytics/kubernetes/materialization/_pending.html')

    assert 'macro render' in notice
    assert 'status_label(' in pending
    assert 'status_indicator_label(' not in pending
