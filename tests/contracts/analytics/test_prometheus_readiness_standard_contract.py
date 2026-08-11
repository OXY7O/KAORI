import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_all_prometheus_backed_analytics_pages_use_shared_readiness_workspace() -> None:
    for relative in (
        'app/templates/analytics/utilization/partials/_readiness_scope.html',
        'app/templates/analytics/capacity/partials/_controls_readiness.html',
        'app/templates/analytics/storage/partials/_controls_readiness.html',
        'app/templates/analytics/workload/partials/_controls_readiness.html',
        'app/templates/analytics/forecast/partials/_controls_readiness.html',
        'app/templates/analytics/top_consumers/partials/_controls_readiness.html',
    ):
        source = read(relative)
        assert 'analytics_workspace.controls_readiness(' in source
        assert 'prometheus_status' in source
        assert 'Prometheus Status' not in source


def test_shared_prometheus_card_owns_canonical_data_and_geometry() -> None:
    source = read('app/templates/analytics/components/_prometheus_status.html')

    for marker in (
        'Prometheus Status',
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


def test_overview_reuses_same_prometheus_card_and_snapshot_card() -> None:
    source = read('app/templates/analytics/overview/partials/_health_summary.html')
    workspace = read('app/templates/analytics/components/_analysis_workspace.html')

    assert 'analytics_workspace.prometheus_card(payload.prometheus)' in source
    assert 'analytics_workspace.snapshot_card(' in source
    assert 'prometheus_status_panel.render(status)' in workspace
    assert 'payload.last_analyzed_at' not in source


def test_forecast_control_groups_are_equal_peer_surfaces() -> None:
    source = read('app/templates/analytics/forecast/partials/_controls_readiness.html')
    workspace = read('app/templates/analytics/components/_analysis_workspace.html')

    assert 'xl:grid-cols-2' in source
    assert source.count('analytics_workspace.control_group(') == 2
    assert "'forecast-scope-controls'" in source
    assert "'forecast-projection-controls'" in source
    assert 'min-h-16' in workspace
    assert 'xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]' not in source


def test_legacy_analytics_controls_component_is_removed() -> None:
    assert not (ROOT / 'app/templates/analytics/components/_controls.html').exists()


def test_prometheus_status_builders_use_the_canonical_presenter() -> None:
    for relative in (
        'app/analytics/common/base_service.py',
        'app/analytics/common/context.py',
        'app/analytics/capacity/service.py',
        'app/analytics/storage/service.py',
        'app/analytics/utilization/service.py',
        'app/analytics/workload/service.py',
        'app/analytics/overview/service.py',
    ):
        assert 'present_prometheus_status' in read(relative)
