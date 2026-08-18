from app.storage.object_storage.inventory.tasks import _build_result


def _result(*, total: int, synced: int, failed: list[str], buckets: int = 0):
    return _build_result(
        requested_by_user_id=7,
        total_count=total,
        synced_count=synced,
        bucket_count=buckets,
        failed_systems=failed,
        started_at='2026-08-13T00:00:00+00:00',
        duration_seconds=2.5,
    )


def test_object_storage_inventory_result_reports_success() -> None:
    result = _result(total=2, synced=2, failed=[], buckets=14)
    assert result['status'] == 'success'
    assert result['synced_count'] == 2
    assert result['bucket_count'] == 14
    assert 'latest committed object-storage snapshots' in result['detail']


def test_object_storage_inventory_result_reports_partial_failure_without_hiding_snapshot_safety() -> None:
    result = _result(total=3, synced=2, failed=['Storage B'], buckets=10)
    assert result['status'] == 'warning'
    assert result['failed_count'] == 1
    assert 'Existing committed snapshots remain available' in result['detail']


def test_object_storage_inventory_result_reports_all_failed() -> None:
    result = _result(total=2, synced=0, failed=['Storage A', 'Storage B'])
    assert result['status'] == 'error'
    assert result['failed_count'] == 2
    assert 'All 2 eligible object-storage systems failed' in result['message']
