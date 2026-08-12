from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_storage_navigation_is_domain_first_and_vendor_neutral() -> None:
    sidebar = read('app/templates/components/navigation/sidebar.html')
    menu = read('app/templates/components/navigation/object_storage_menu.html')

    assert '>Storage<' in sidebar
    assert 'Object Storage' in menu
    assert '>Overview<' in menu
    assert '>Systems<' in menu
    assert '>Buckets<' in menu
    assert 'MinIO' not in menu
    assert "object_storage_inventory.overview" in menu
    assert "object_storage_inventory.systems" in menu
    assert "object_storage_inventory.buckets" in menu


def test_object_storage_inventory_is_registered_as_read_only_inventory_domain() -> None:
    blueprints = read('app/bootstrap/blueprints.py')
    routes = read('app/storage_inventory/routes.py')

    assert 'object_storage_inventory_bp' in blueprints
    assert "url_prefix='/storage/object-storage'" in routes
    assert routes.count("@permission_required('inventory.view')") >= 5
    assert "@object_storage_inventory_bp.get('/')" in routes
    assert "@object_storage_inventory_bp.get('/systems')" in routes
    assert "@object_storage_inventory_bp.get('/buckets')" in routes


def test_bucket_inventory_is_committed_snapshot_not_live_page_discovery() -> None:
    model = read('app/models/object_storage.py')
    sync = read('app/storage_inventory/sync.py')
    adapter = read('app/integrations/minio/adapter.py')
    overview = read('app/templates/object_storage_inventory/overview/partials/_snapshot_boundary.html')
    buckets = read('app/templates/object_storage_inventory/buckets/partials/_table_card.html')

    assert 'class ObjectStorageBucket' in model
    assert 'object_storage_buckets' in model
    assert 'inventory_observed_at' in model
    assert 'commit_bucket_inventory' in sync
    assert 'commit_bucket_inventory(' in adapter
    assert 'Full Validation owns S3 discovery' in sync
    assert 'snapshot_context_bar.render' in overview
    assert 'overview.snapshot.source_label' in overview
    assert 'No live S3 query' in buckets


def test_object_storage_inventory_keeps_kaori_table_and_pagination_standard() -> None:
    systems = read('app/templates/object_storage_inventory/systems/partials/_table_content.html')
    buckets = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    systems_filters = read('app/templates/object_storage_inventory/systems/partials/_table_card.html')
    buckets_filters = read('app/templates/object_storage_inventory/buckets/partials/_table_card.html')

    for template in (systems, buckets):
        assert 'table_ui.table_classes(' in template
        assert 'pagination_ui.footer_classes()' in template
        assert 'pagination_ui.numeric_pages(' in template
        assert 'Rows Per Page' in template
        assert "components/states/_empty_state.html" in template
        assert 'resource_detail_modal.detail_button' in template
    assert 'object-storage-systems-loading' in systems_filters
    assert 'object-storage-buckets-loading' in buckets_filters


def test_v1_bucket_scope_is_explicitly_identity_first() -> None:
    detail = read('app/templates/object_storage_inventory/buckets/partials/_bucket_detail_content.html')

    assert 'Bucket Identity' in detail
    assert 'Discovery Evidence' in detail
    assert 'Versioning, lifecycle, policy, retention, encryption, and replication evidence' in detail
    assert 'will be added as dedicated inventory contracts' in detail


def test_object_storage_bucket_migration_follows_minio_provider_branch() -> None:
    migration = read('migrations/versions/20260812_object_storage_inventory.py')

    assert "revision = '20260812_obj_storage_inv'" in migration
    assert "down_revision = '20260812_minio_owner_cleanup'" in migration
    assert "'object_storage_buckets'" in migration
    assert "'inventory_observed_at'" in migration
    assert "'uq_object_storage_bucket_system_name'" in migration
