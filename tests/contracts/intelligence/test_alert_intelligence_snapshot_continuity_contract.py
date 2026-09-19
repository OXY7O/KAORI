from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_external_snapshot_adapter_is_preserved_but_not_scheduled_for_alert_management() -> None:
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    worker = read('app/platform_operations/notifications/alert_delivery/tasks.py')
    service = read('app/intelligence/alert_intelligence/service.py')

    # Future-ready adapter stays available for a later explicit external-alert ingestion phase.
    assert 'load_snapshot_rows' in lifecycle
    assert "if not snapshot.get('available') or snapshot.get('serving_last_good')" in lifecycle
    # Current Alert Management scope is KAORI recommendation-origin only.
    assert 'reconcile_alert_cases()' not in worker
    assert 'reconcile_recommendation_alert_cases()' in worker
    assert "AlertCase.source_type == 'recommendation'" in service
    assert 'load_alerts_by_source' not in service
    assert 'load_alert_stream' not in service


def test_provider_last_good_state_cannot_drive_current_kaori_alert_lifecycle() -> None:
    snapshots = read('app/intelligence/alert_intelligence/snapshots.py')
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    worker = read('app/platform_operations/notifications/alert_delivery/tasks.py')
    candidates = read('app/intelligence/automation_control/candidates.py')

    assert 'serving_last_good' in snapshots
    assert "snapshot.get('serving_last_good')" in lifecycle
    assert 'reconcile_alert_cases()' not in worker
    assert "AlertCase.source_type == 'recommendation'" in candidates
    assert 'list_active_alert_events' not in candidates
    assert 'source_resolved' in lifecycle
    assert 'verification_pending' in lifecycle
