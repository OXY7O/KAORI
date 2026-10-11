"""Source-level locks for the bounded SQL list contract. Runtime DB UAT remains separate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_lists_filter_before_sql_pagination() -> None:
    source = read('app/storage/object_storage/inventory/presentation.py')
    assert 'from app.common.pagination import paginate_query' in source
    assert 'paginate_sequence(' not in source
    assert 'def _filtered_systems(filters: SystemFilters)' in source
    assert 'def _filtered_buckets(filters: BucketFilters)' in source
    assert 'query = _filtered_systems(filters)' in source
    assert 'query = _filtered_buckets(filters)' in source
    assert source.count('paged, pagination = paginate_query(') == 2
    assert "ObjectStorageSystem.id.asc()" in source
    assert "ObjectStorageBucket.id.asc()" in source


def test_object_storage_aggregate_snapshots_and_filters_do_not_materialize_fleet_orm_rows() -> None:
    source = read('app/storage/object_storage/inventory/presentation.py')
    assert 'def _committed_system_snapshot()' in source
    assert "func.count(ObjectStorageSystem.inventory_observed_at)" in source
    assert "'snapshot': _committed_system_snapshot()" in source
    assert "func.count(func.distinct(ObjectStorageBucket.object_storage_system_id))" in source
    assert "func.count(func.distinct(IntegrationInstance.provider_key))" in source
    assert 'def _system_options()' in source
    assert '.distinct().all()' in source
    assert 'def _join_system_owner(query)' in source
    assert "identity.metadata_json['asset_key'].as_string()" in source
    assert 'ObjectStorageBucket.query.count()' in source
    assert 'selectinload(ObjectStorageSystem.buckets)' in source
    assert 'joinedload(ObjectStorageBucket.object_storage_system)' in source


def test_object_storage_source_preserves_shared_pagination_and_modal_contract() -> None:
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    for table in (systems, buckets):
        assert 'pagination_ui.numeric_pages(' in table
        assert 'resource_detail_modal.detail_button(' in table
        assert 'name="per_page"' in table
        assert 'data-kaori-auto-submit' in table
        assert 'partial_mode' in table
