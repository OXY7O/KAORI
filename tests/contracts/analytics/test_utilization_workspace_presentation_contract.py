from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_utilization_scope_and_snapshot_are_outside_tab_workspace() -> None:
    index = (ROOT / 'app/templates/analytics/utilization/index.html').read_text()
    readiness = (
        ROOT / 'app/templates/analytics/utilization/partials/_readiness_scope.html'
    ).read_text()

    assert 'analytics/utilization/partials/_readiness_scope.html' in index
    assert index.index('analytics/utilization/partials/_readiness_scope.html') < index.index(
        'Resource Utilization Workspace'
    )
    assert 'Utilization Scope &amp; Data Readiness' in readiness
    assert 'Prometheus Status' not in index
    assert 'Active Cluster Scope' in readiness
    assert 'Latest Utilization Data Snapshot' in readiness
    assert 'Latest Data Sync' in readiness
    assert 'Latest Worker Attempt' in readiness
    assert 'Freshness Window' in readiness


def test_utilization_tabs_and_content_share_one_workspace_box() -> None:
    index = (ROOT / 'app/templates/analytics/utilization/index.html').read_text()

    assert 'Resource Utilization Workspace' in index
    assert "embedded=true" in index
    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' in index
    assert 'utilization-content-panel-summary' in index
    assert 'utilization-content-panel-trend' in index
    assert 'utilization-content-panel-nodes' in index
    assert 'utilization-content-panel-recommendations' in index


def test_utilization_trend_has_operational_summary() -> None:
    trend = (
        ROOT / 'app/templates/analytics/utilization/partials/_trend.html'
    ).read_text()
    materialization = (
        ROOT / 'app/analytics/utilization/materialization.py'
    ).read_text()

    assert 'Trend Posture' in trend
    assert 'Current utilization' in trend
    assert 'Average' in trend
    assert 'Peak' in trend
    assert 'Historical Signal Behavior' in trend
    assert 'build_utilization_trend_summary' in materialization
    assert "'current': round(values[-1], 2)" in materialization
    assert "'average': round(sum(values) / len(values), 2)" in materialization
    assert "'peak': round(max(values), 2)" in materialization


def test_snapshot_metadata_exposes_latest_worker_attempt() -> None:
    presentation = (
        ROOT / 'app/analytics/materialization/presentation.py'
    ).read_text()

    assert "'dataset_key': snapshot.dataset_key if snapshot else None" in presentation
    assert "'last_attempt_at': snapshot.last_attempt_at if snapshot else None" in presentation
    assert "'last_job_execution_id': snapshot.last_job_execution_id if snapshot else None" in presentation
