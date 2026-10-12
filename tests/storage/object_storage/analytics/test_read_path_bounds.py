from __future__ import annotations

from pathlib import Path


def test_analytics_selector_does_not_eagerly_load_fleet_buckets() -> None:
    root = Path(__file__).resolve().parents[4]
    source = (root / 'app/storage/object_storage/analytics/service.py').read_text(encoding='utf-8')
    selector = source.split('def _systems(', 1)[1].split('def _selected_system(', 1)[0]
    assert 'load_only(' in selector
    assert 'ObjectStorageSystem.inventory_observed_at' in selector
    assert 'selectinload(ObjectStorageSystem.buckets)' not in selector
    assert '.buckets' not in selector


def test_every_analytics_page_and_record_fragment_reads_committed_snapshot() -> None:
    root = Path(__file__).resolve().parents[4]
    source = (root / 'app/storage/object_storage/analytics/service.py').read_text(encoding='utf-8')
    assert 'context, system, time_range = _base_context(page_key, query_args)' in source
    assert '_attach_committed_analytics_snapshot(context, system=system, time_range=time_range)' in source
    for method in ('get_object_storage_alert_table_context', 'get_object_storage_bucket_table_context',
                   'get_object_storage_bucket_forecast_table_context'):
        assert f'def {method}(' in source
