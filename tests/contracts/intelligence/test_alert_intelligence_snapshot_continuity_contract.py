from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_operations_lifecycle_consumes_only_fresh_committed_snapshots() -> None:
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'load_snapshot_rows' in lifecycle
    assert "if not snapshot.get('available') or snapshot.get('serving_last_good')" in lifecycle
    assert "stats['skipped'] += 1" in lifecycle
    assert 'load_snapshot_rows' in service
    assert 'load_alerts_by_source' not in service
    assert 'load_alert_stream' not in service


def test_last_good_snapshot_remains_readable_but_cannot_drive_lifecycle_transition() -> None:
    snapshots = read('app/intelligence/alert_intelligence/snapshots.py')
    lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')

    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'serving_last_good' in snapshots
    assert "snapshot.get('serving_last_good')" in lifecycle
    assert "snapshot.get('serving_last_good')" in service
    assert "if not status.get('connected')" in service
    assert 'source_resolved' in lifecycle
    assert 'verification_pending' in lifecycle
