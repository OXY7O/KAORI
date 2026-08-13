from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_systems_route_only_passes_fields_owned_by_system_filters() -> None:
    routes = read('app/storage_inventory/routes.py')
    presentation = read('app/storage_inventory/presentation.py')

    systems_block = routes.split('def systems() -> ResponseReturnValue:', 1)[1].split(
        "@object_storage_inventory_bp.get('/systems/<string:system_id>/details')", 1
    )[0]
    system_filters = presentation.split('class SystemFilters:', 1)[1].split('def build_systems', 1)[0]

    assert "native_type=request.args.get('native_type'" not in systems_block
    assert 'selected_native_type' not in systems_block
    assert 'native_type:' not in system_filters


def test_bucket_route_keeps_native_type_filter_for_bucket_and_container_inventory() -> None:
    routes = read('app/storage_inventory/routes.py')
    presentation = read('app/storage_inventory/presentation.py')

    buckets_block = routes.split('def buckets() -> ResponseReturnValue:', 1)[1].split(
        "@object_storage_inventory_bp.get('/buckets/<int:bucket_id>/details')", 1
    )[0]
    bucket_filters = presentation.split('class BucketFilters:', 1)[1].split('def build_buckets', 1)[0]

    assert "native_type=request.args.get('native_type'" in buckets_block
    assert 'selected_native_type=filters.native_type' in buckets_block
    assert 'native_type: str' in bucket_filters
