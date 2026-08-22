from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_intelligence_web_payload_is_committed_snapshot_only() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')
    snapshots = read('app/intelligence/alert_intelligence/snapshots.py')

    assert 'load_snapshot_rows' in service
    assert 'load_alerts_by_source' not in service
    assert 'load_alert_stream' not in service
    assert "dataset_key='analytics.alerts'" in snapshots
    assert 'read_last_known_snapshot' in snapshots
    assert 'read_latest_known_analytics_snapshot' in snapshots
    assert 'resolve_materialized_alert_stream' in snapshots


def test_last_good_snapshot_readers_preserve_committed_payload_after_refresh_failure() -> None:
    kubernetes = read('app/kubernetes/analytics/materialization/service.py')
    object_storage = read('app/storage/object_storage/analytics/materialization.py')

    assert 'def read_last_known_snapshot(' in kubernetes
    assert "if snapshot.status == 'failed':" in kubernetes
    assert "state = 'failed'" in kubernetes
    assert 'return SnapshotResult(context, snapshot, state, now > expires_at)' in kubernetes

    assert 'def read_latest_known_analytics_snapshot(' in object_storage
    assert 'ObjectStorageAnalyticsSnapshot.payload_json.is_not(None)' in object_storage
    assert 'ObjectStorageAnalyticsSnapshot.generated_at.is_not(None)' in object_storage
    assert "state['last_known_available']" in object_storage
    assert 'return payload, state' in object_storage


def test_alert_intelligence_surfaces_snapshot_freshness_without_blocking_provider_calls() -> None:
    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')

    assert 'payload.snapshot.label' in page
    assert 'payload.snapshot.label' in summary
    assert 'payload.snapshot.label' in workspace
    assert 'Snapshot State' in alerts
    assert 'Last Successful' in alerts
    assert 'Last Good Snapshot Active' in alerts
    assert 'Page requests never wait for provider connectivity' in alerts
    assert 'background refresh is stale, still running, or failed' in alerts
    assert 'this page does not contact the provider directly' in alerts


def test_stale_last_good_evidence_is_ui_continuity_only_not_automation_input() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "if not status.get('connected') or snapshot.get('serving_last_good'):" in service
    assert service.count("snapshot.get('serving_last_good')") >= 2
