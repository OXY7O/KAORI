from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_systems_table_is_final_canonical_inventory_contract() -> None:
    table = read('app/templates/inventory/object_storage/systems/partials/_table_content.html')
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
    assert 'system.compatibility_profile_label' in table
    assert "width='2xl'" in table
    assert 'side_drawer.render(' in table
    assert 'resource_detail_modal' not in table


def test_systems_drawer_has_operational_reading_and_authority_boundary() -> None:
    table = read('app/templates/inventory/object_storage/systems/partials/_table_content.html')
    assert "'Operational Reading'" in table
    assert 'Provider Ready' in table
    assert 'Snapshot Current' in table
    assert 'Inventory Coverage' in table
    assert 'Authority Boundary' in table
    assert 'Related Operational Workspace' in table
    assert "job_key='object_storage.inventory.sync'" in table
    assert 'Open Inventory Job' in table
    assert 'does not query the provider API live' not in table  # wording moved to explicit authority boundary
    assert 'reads committed Object Storage Inventory data' in table


def test_systems_workspace_keeps_kaori_hero_summary_filter_and_job_ownership() -> None:
    hero = read('app/templates/inventory/object_storage/systems/partials/_hero.html')
    summary = read('app/templates/inventory/object_storage/systems/partials/_summary_cards.html')
    table_card = read('app/templates/inventory/object_storage/systems/partials/_table_card.html')
    assert 'page_hero.shell_classes()' in hero
    assert 'Object Storage Systems Posture' in hero
    assert 'operational_section_card.render(' in summary
    assert 'posture_grid.render(' in summary
    assert 'table_ui.inventory_block_header(' in table_card
    assert "job_key='object_storage.inventory.sync'" in table_card
    assert 'Manage Inventory Jobs' in table_card
    assert 'No live provider query is issued by this page.' in table_card


def test_object_storage_templates_do_not_add_local_style_debt() -> None:
    systems = read('app/templates/inventory/object_storage/systems/partials/_table_content.html')
    buckets = read('app/templates/inventory/object_storage/buckets/partials/_table_content.html')
    assert 'text-[' not in systems
    assert 'text-[' not in buckets
    assert 'tracking-[' not in buckets
    assert 'operational_section_card.render(' in buckets
    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' not in buckets
