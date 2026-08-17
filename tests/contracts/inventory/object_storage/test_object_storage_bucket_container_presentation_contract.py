from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_bucket_container_page_keeps_one_vendor_neutral_inventory_surface() -> None:
    menu = read('app/templates/components/navigation/object_storage_menu.html')
    hero = read('app/templates/inventory/object_storage/buckets/partials/_hero.html')
    table = read('app/templates/inventory/object_storage/buckets/partials/_table_content.html')

    assert 'Buckets &amp; Containers' in menu
    assert 'Buckets &amp; Containers' in hero
    assert 'MinIO' not in menu
    assert 'AWS' not in menu
    assert 'Azure' not in menu
    assert 'Ceph' not in menu
    for heading in (
        'Name',
        'System',
        'Provider',
        'Type',
        'Location',
        'Quota',
        'Protection',
        'Last Snapshot',
        'Details',
    ):
        assert heading in table


def test_list_table_stays_canonical_while_modal_is_provider_aware() -> None:
    index = read('app/templates/inventory/object_storage/buckets/index.html')
    table = read('app/templates/inventory/object_storage/buckets/partials/_table_content.html')
    presentation = read('app/inventory/object_storage/presentation.py')

    assert 'resource_detail_modal' not in index
    assert 'resource_detail_modal' not in table
    assert 'x-teleport="body"' in table
    assert 'max-w-[88rem]' in table
    assert 'View Details' in table
    assert 'Inventory Snapshot' in table
    assert 'Asset Context' in table
    assert 'Provider Context' in table
    assert 'Protection & Access' in table
    assert 'Lifecycle & Replication' in table
    assert 'Used Size' in table
    assert 'provider_detail_sections' in table
    assert '_provider_detail_sections' in presentation
    assert 'Native Provider Evidence' not in presentation


def test_provider_specific_metadata_does_not_leak_into_the_general_table_contract() -> None:
    model = read('app/models/object_storage.py')
    presentation = read('app/inventory/object_storage/presentation.py')
    table = read('app/templates/inventory/object_storage/buckets/partials/_table_content.html')

    for field in (
        'native_type',
        'location',
        'versioning_state',
        'immutability_state',
        'encryption_state',
        'lifecycle_state',
        'replication_state',
        'access_policy_state',
        'exposure_state',
        'provider_metadata',
        'quota_bytes',
        'quota_state',
        'quota_observed_at',
    ):
        assert field in model
    assert "'provider_metadata': provider_metadata" in presentation
    assert 'provider_metadata' not in table
    assert 'API Endpoint' not in table.split('<thead', 1)[1].split('</thead>', 1)[0]
    assert 'Compatibility Profile' not in table.split('<thead', 1)[1].split('</thead>', 1)[0]


def test_minio_inventory_collector_emits_provider_neutral_namespace_contract() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    sync = read('app/inventory/object_storage/sync.py')

    assert "native_type: str = 'bucket'" in client
    assert 'location: str | None = None' in client
    assert "versioning_state: str = 'not_collected'" in client
    assert 'provider_metadata: dict[str, Any] = field(default_factory=dict)' in client
    assert "bucket.native_type = summary.native_type or 'bucket'" in sync
    assert 'bucket.location = summary.location' in sync
    assert 'bucket.provider_metadata = dict(summary.provider_metadata or {})' in sync


def test_bucket_container_schema_migration_follows_current_inventory_job_head() -> None:
    migration = read('migrations/versions/20260813_object_storage_bucket_container_contract.py')

    assert "revision = '20260813_obj_asset_contract'" in migration
    assert "down_revision = '20260813_inventory_op_names'" in migration
    assert "'object_storage_buckets'" in migration
    assert "'native_type'" in migration
    assert "'provider_metadata'" in migration
    assert "'versioning_state'" in migration
    assert "'exposure_state'" in migration


def test_bucket_container_filters_use_system_provider_type_and_search() -> None:
    routes = read('app/inventory/object_storage/routes.py')
    card = read('app/templates/inventory/object_storage/buckets/partials/_table_card.html')
    presentation = read('app/inventory/object_storage/presentation.py')

    assert "native_type=request.args.get('native_type'" in routes
    assert 'selected_native_type=filters.native_type' in routes
    assert '>Provider<' in card
    assert '>Type<' in card
    assert 'Search Assets' in card
    assert "'types': [" in presentation
    assert "and (not filters.native_type or row['native_type'] == filters.native_type)" in presentation
