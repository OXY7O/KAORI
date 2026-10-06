import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_all_metrics_source_backed_analytics_pages_use_shared_readiness_workspace() -> None:
    for relative in (
        'app/templates/kubernetes/analytics/utilization/partials/_readiness_scope.html',
        'app/templates/kubernetes/analytics/capacity/partials/_controls_readiness.html',
        'app/templates/kubernetes/analytics/storage/partials/_controls_readiness.html',
        'app/templates/kubernetes/analytics/workload/partials/_controls_readiness.html',
        'app/templates/kubernetes/analytics/forecast/partials/_controls_readiness.html',
        'app/templates/kubernetes/analytics/top_consumers/partials/_controls_readiness.html',
    ):
        source = read(relative)
        assert 'analytics_workspace.controls_readiness(' in source
        assert 'metrics_source_status' in source
        assert 'Metrics Source Status' not in source


def test_shared_metrics_source_card_owns_canonical_data_and_geometry() -> None:
    source = read('app/templates/kubernetes/analytics/components/_metrics_source_status.html')

    for marker in (
        'Metrics Source Status',
        'Query Ready',
        'Query Degraded',
        'Unavailable',
        'Not Configured',
        'Waiting for Cluster',
        'Response',
        'Checked At',
        'status.last_checked_at',
    ):
        assert marker in source

    assert re.search(r'user_datetime\(["\']Not Recorded["\']\)', source)
    assert 'materialization' not in source
    assert 'last_analyzed_at' not in source
    assert 'flat=' not in source
    assert 'compact=' not in source


def test_overview_reuses_same_metrics_source_card_and_snapshot_card() -> None:
    source = read('app/templates/kubernetes/analytics/overview/partials/_health_summary.html')
    workspace = read('app/templates/kubernetes/analytics/components/_analysis_workspace.html')

    assert 'analytics_workspace.metrics_source_card(payload.metrics_source)' in source
    assert 'analytics_workspace.snapshot_card(' in source
    assert 'metrics_source_status_panel.render(status)' in workspace
    assert 'payload.last_analyzed_at' not in source


def test_forecast_control_groups_are_equal_peer_surfaces() -> None:
    source = read('app/templates/kubernetes/analytics/forecast/partials/_controls_readiness.html')
    workspace = read('app/templates/kubernetes/analytics/components/_analysis_workspace.html')

    assert 'xl:grid-cols-2' in source
    assert source.count('analytics_workspace.control_group(') == 2
    assert "'forecast-scope-controls'" in source
    assert "'forecast-projection-controls'" in source
    assert 'min-h-16' in workspace
    assert 'xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]' not in source


def test_legacy_analytics_controls_component_is_removed() -> None:
    assert not (ROOT / 'app/templates/analytics/components/_controls.html').exists()


def test_metrics_source_status_builders_use_the_canonical_presenter() -> None:
    for relative in (
        'app/kubernetes/analytics/common/base_service.py',
        'app/kubernetes/analytics/common/context.py',
        'app/kubernetes/analytics/capacity/service.py',
        'app/kubernetes/analytics/storage/service.py',
        'app/kubernetes/analytics/utilization/service.py',
        'app/kubernetes/analytics/workload/service.py',
        'app/kubernetes/analytics/overview/service.py',
    ):
        assert 'present_metrics_source_status' in read(relative)
