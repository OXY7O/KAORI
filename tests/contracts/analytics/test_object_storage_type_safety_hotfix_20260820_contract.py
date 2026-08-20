from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_snapshot_readers_narrow_optional_mapping_payloads() -> None:
    bucket = read('app/storage/object_storage/analytics/bucket_evidence.py')
    service = read('app/storage/object_storage/analytics/service.py')

    assert "forecast_value = raw.get('forecast')" in bucket
    assert 'forecast = cast(dict[str, Any], forecast_value) if isinstance(forecast_value, dict) else {}' in bucket
    assert "streams_value = payload.get('alert_streams')" in service
    assert 'streams = cast(dict[str, Any], streams_value) if isinstance(streams_value, dict) else {}' in service
    assert service.count("page_metrics_value = payload.get('page_metrics')") >= 2
    assert (
        service.count(
            'page_metrics = cast(dict[str, Any], page_metrics_value) if isinstance(page_metrics_value, dict) else {}'
        )
        >= 2
    )


def test_object_storage_dashboard_filters_optional_inventory_timestamps_before_max() -> None:
    service = read('app/storage/object_storage/dashboard/service.py')

    assert 'def _inventory_observation_times(systems: list[ObjectStorageSystem]) -> list[datetime]:' in service
    assert 'if resolved is not None:' in service
    assert 'observed.append(resolved)' in service
    assert 'observed = _inventory_observation_times(systems)' in service
    assert 'max(_inventory_observation_times(systems), default=None)' in service
