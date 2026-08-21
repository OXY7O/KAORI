from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_systems_table_is_final_canonical_inventory_contract() -> None:
    table = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
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
    assert 'resource_detail_modal.detail_button(' in table
    assert 'side_drawer.render(' not in table
    assert 'system.compatibility_profile_label' in detail


def test_system_detail_has_operational_guidance_and_authority_boundary() -> None:
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
    table_card = read('app/templates/storage/object_storage/inventory/systems/partials/_table_card.html')

    assert 'Authority Boundary' in detail
    assert 'reads committed Object Storage Inventory data' in detail
    assert 'system.guidance.title' in detail
    assert 'system.guidance.description' in detail
    assert "detail.inventory_section('Inventory Snapshot'" in detail
    assert 'Registered storage system identity, environment, provider release, and compatibility profile.' in detail
    assert "job_key='object_storage.inventory.sync'" in table_card
    assert 'Manage Inventory Jobs' in table_card


def test_systems_workspace_keeps_kaori_hero_summary_filter_and_job_ownership() -> None:
    hero = read('app/templates/storage/object_storage/inventory/systems/partials/_hero.html')
    summary = read('app/templates/storage/object_storage/inventory/systems/partials/_summary_cards.html')
    table_card = read('app/templates/storage/object_storage/inventory/systems/partials/_table_card.html')
    assert 'page_hero.shell_classes()' in hero
    assert 'Object Storage Systems Posture' in hero
    assert 'operational_section_card.render(' in summary
    assert 'posture_grid.render(' in summary
    assert 'table_ui.inventory_block_header(' in table_card
    assert "job_key='object_storage.inventory.sync'" in table_card
    assert 'Manage Inventory Jobs' in table_card
    assert 'No live provider query is issued by this page.' in table_card


def test_object_storage_templates_do_not_add_local_style_debt() -> None:
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    system_detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
    bucket_detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    for template in (systems, buckets, system_detail, bucket_detail):
        assert 'text-[' not in template
        assert 'tracking-[' not in template
    assert 'operational_section_card.render(' not in bucket_detail
    assert 'side_drawer.render(' not in systems
    assert 'x-teleport="body"' not in buckets


def test_system_detail_uses_unified_resource_sheet_v10() -> None:
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
    assert 'data-kaori-inventory-detail="v10"' in detail
    assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail
    assert 'detail.workspace_header(' in detail
    assert 'detail.inventory_title(' in detail
    assert 'detail.inspector_summary_strip(' in detail
    assert 'detail.resource_sheet()' in detail
    assert "detail.inventory_section('System Identity'" in detail
    assert "detail.inventory_section('Provider Connection'" in detail
    assert "detail.inventory_section('Inventory Snapshot'" in detail
    assert 'Registered storage system identity, environment, provider release, and compatibility profile.' in detail
    assert 'detail.detail_card(' not in detail
