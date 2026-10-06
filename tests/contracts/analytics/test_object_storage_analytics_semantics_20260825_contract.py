from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_overview_has_alerts_tab_and_no_recommendations_tab() -> None:
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    assert "('alerts', 'Alerts', 'bell-ring')" in overview
    assert 'object-storage-overview-content-panel-alerts' in overview
    assert 'object-storage-overview-content-panel-recommendations' not in overview


def test_overview_alerts_use_provider_and_anomaly_evidence_not_intelligence() -> None:
    source = read('app/storage/object_storage/analytics/overview_alerts.py')
    assert 'resolve_materialized_alert_stream' in source
    assert 'build_alert_posture' in source
    assert "page_metrics.get('alerts')" in source
    assert 'AlertCase' not in source
    assert 'get_active_recommendation_findings' not in source


def test_alerts_workspace_separates_provider_alerts_anomaly_signals_and_recommendations() -> None:
    workspace = read('app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html')
    assert "('records', 'Provider Alerts', 'bell-ring')" in workspace
    assert "('signals', 'Anomaly Signals', 'list-tree')" in workspace
    assert "('recommendations', 'Recommendations', 'list-checks')" in workspace
    assert "('records', 'Alert Records'" not in workspace
    assert "('signals', 'Metric Signals'" not in workspace


def test_alerts_workspace_keeps_unknown_when_provider_evidence_is_unavailable() -> None:
    summary = read('app/templates/storage/object_storage/analytics/partials/_alerts_summary.html')
    assert 'Unknown' in summary
    assert 'Provider Alerts' in summary
    assert 'Anomaly Signals' in summary
