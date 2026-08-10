from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_utilization_scope_and_snapshot_are_outside_tab_workspace() -> None:
    index = read('app/templates/analytics/utilization/index.html')
    readiness = read('app/templates/analytics/utilization/partials/_readiness_scope.html')

    assert 'analytics/utilization/partials/_readiness_scope.html' in index
    assert index.index('analytics/utilization/partials/_readiness_scope.html') < index.index(
        'Resource Utilization Workspace'
    )
    assert 'Utilization Controls & Data Readiness' in readiness
    assert 'Prometheus Status' not in index
    assert 'Active Cluster' in readiness
    assert 'controls_readiness' in readiness
    assert 'analytics_materialization' in readiness
    assert 'Worker Attempt' in read('app/templates/analytics/components/_analysis_workspace.html')
    assert 'bg-surface-hover px-4 py-4 sm:grid-cols-2 xl:grid-cols-4' not in readiness


def test_utilization_uses_shared_workspace_and_has_no_composite_tracker() -> None:
    index = read('app/templates/analytics/utilization/index.html')

    assert 'analytics_workspace.tabbed(' in index
    assert 'Resource Utilization Workspace' in index
    assert 'utilization-content-panel-summary' in index
    assert 'utilization-content-panel-trend' in index
    assert 'utilization-content-panel-nodes' in index
    assert 'utilization-content-panel-recommendations' in index
    assert 'utilization-load-tracker' not in index
    assert 'analytics/partials/_load_tracker.html' not in index


def test_heavy_utilization_tabs_load_only_after_activation() -> None:
    index = read('app/templates/analytics/utilization/index.html')
    controls = read('app/static/js/analytics_controls.js')
    routes = read('app/analytics/utilization/routes.py')

    assert index.count('hx-trigger="kaori:analytics-tab-activated once"') == 2
    assert "url_for('analytics.utilization_trend'" in index
    assert "url_for('analytics.utilization_node_detail'" in index
    assert 'activationTargets' in controls
    assert "window.htmx.trigger(target, 'kaori:analytics-tab-activated')" in controls
    assert 'notifyAnalyticsTabVisible' in controls
    assert "new CustomEvent('kaori:analytics-tab-visible'" in controls
    assert 'clearLegacyAnalyticsHash' not in controls
    assert 'window.location.hash' not in controls
    assert "searchParams.get('tab')" in controls
    assert 'partials/_trend_pending.html' in routes
    assert 'partials/_node_pending.html' in routes


def test_summary_and_node_detail_use_shared_resource_pressure_lanes() -> None:
    summary = read('app/templates/analytics/utilization/partials/_current_summary.html')
    node = read('app/templates/analytics/utilization/partials/_node_detail.html')
    lane = read('app/templates/analytics/components/_resource_pressure_lane.html')

    assert 'Resource Pressure Detail' in summary
    assert 'pressure_lane.render' in summary
    assert 'pressure_lane.render' in node
    assert 'Remaining Headroom' in lane
    assert 'Operational Reading' in lane
    assert 'used_capacity' in lane


def test_utilization_trend_is_bright_has_visible_legend_and_external_js() -> None:
    trend = read('app/templates/analytics/utilization/partials/_trend.html')
    script = read('app/static/js/analytics_utilization.js')
    legend = read('app/templates/analytics/components/_chart_legend.html')

    assert 'Current Highest' in trend
    assert 'Peak Signal' in trend
    assert 'Historical Signal Behavior' in trend
    assert 'Resource Trend Outlook' in trend
    assert 'chart_legend.render' in trend
    assert 'data-utilization-trend-data' in trend
    assert '<script>' not in trend
    assert 'new Chart' in script
    assert 'htmx:afterSwap' in script
    assert 'htmx:afterSettle' in script
    assert 'kaori:analytics-tab-visible' in script
    assert 'isTrendRenderable' in script
    assert 'ResizeObserver' in script
    assert 'MAX_VISIBILITY_RETRIES' in script
    assert 'swatch_class' in legend
    assert "[('CPU', 'bg-kaori-primary'), ('Memory', 'bg-status-normal'), ('Pods', 'bg-status-pending')]" in trend


def test_utilization_uses_canonical_analysis_surfaces_without_compatibility_file() -> None:
    canonical = ROOT / 'app/templates/analytics/components/_analysis_surfaces.html'
    retired = ROOT / ('app/templates/analytics/components/' + '_overview' + '_surfaces.html')
    imports = '\n'.join(path.read_text(encoding='utf-8') for path in (ROOT / 'app/templates/analytics').rglob('*.html'))

    assert canonical.exists()
    assert not retired.exists()
    assert ('analytics/components/' + '_overview' + '_surfaces.html') not in imports
    assert 'snapshot_shell_classes' in canonical.read_text(encoding='utf-8')
    assert 'evidence_shell_classes' in canonical.read_text(encoding='utf-8')


def test_snapshot_metadata_exposes_latest_worker_attempt() -> None:
    presentation = read('app/analytics/materialization/presentation.py')
    assert "'dataset_key': snapshot.dataset_key if snapshot else None" in presentation
    assert "'last_attempt_at': snapshot.last_attempt_at if snapshot else None" in presentation
    assert "'last_job_execution_id': snapshot.last_job_execution_id if snapshot else None" in presentation
