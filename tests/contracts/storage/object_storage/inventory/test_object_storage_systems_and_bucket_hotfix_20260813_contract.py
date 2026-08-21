from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_bucket_detail_does_not_reference_missing_snapshot_state():
    template = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    assert 'asset.snapshot_state' not in template
    assert 'asset.snapshot_status_label' in template
    assert 'asset.snapshot_status_tone' in template


def test_bucket_presentation_exposes_modal_contract_fields():
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    assert "'snapshot_state': {'label': snapshot_status_label, 'tone': snapshot_status_tone}" in presentation
    assert "'public_exposure': exposure" in presentation
    assert "'data_boundary':" in presentation
    assert "'recommended_action':" in presentation


def test_systems_page_uses_shared_resource_detail_modal() -> None:
    index = read('app/templates/storage/object_storage/inventory/systems/index.html')
    table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert 'resource_detail_modal.detail_button(' in table
    assert 'side_drawer.render' not in table
    assert 'openDrawer' not in table


def test_systems_table_uses_canonical_provider_and_snapshot_columns():
    table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    for heading in (
        'System',
        'Provider',
        'Environment',
        'Release',
        'Endpoint',
        'Inventory Assets',
        'Snapshot',
        'Status',
        'Details',
    ):
        assert f'>{heading}<' in table
    assert 'system.endpoint_display' in table
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
    assert 'Buckets & Containers' in detail


def test_systems_workspace_points_manual_sync_to_job_execution():
    card = read('app/templates/storage/object_storage/inventory/systems/partials/_table_card.html')
    assert "job_key='object_storage.inventory.sync'" in card
    assert 'Manage Inventory Jobs' in card
    assert 'No live provider query is issued by this page.' in card
