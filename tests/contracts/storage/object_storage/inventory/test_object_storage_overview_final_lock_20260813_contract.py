from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_overview_final_lock_uses_fleet_posture_and_committed_snapshot_boundary() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    fleet = read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html')
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert '_snapshot_boundary.html' in index
    assert '_fleet_posture.html' in index
    assert 'Fleet Inventory Posture' in fleet
    assert "variant='semantic'" in fleet
    assert '_overview_bucket_posture' in presentation
    assert '_overview_fleet_readings' in presentation
    assert '_overview_provider_distribution' in presentation
    assert "'bucket_posture': bucket_posture" in presentation
    assert "'fleet_readings': _overview_fleet_readings(bucket_posture)" in presentation
    assert "'provider_distribution': _overview_provider_distribution(rows)" in presentation


def test_overview_fleet_posture_covers_quota_protection_exposure_and_usage() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert "'quota_assessed': quota_assessed" in presentation
    assert "'quota_configured': quota_configured" in presentation
    assert "'protection_attention': protection_attention" in presentation
    assert "'public_exposure': public_exposure" in presentation
    assert "'usage_collected': usage_collected" in presentation
    assert 'Quota Assessed' in presentation
    assert 'Protection Attention' in presentation
    assert 'Public Exposure' in presentation
    assert 'Usage Collected' in presentation


def test_overview_system_details_match_systems_final_authority_boundary() -> None:
    index = read('app/templates/storage/object_storage/inventory/overview/index.html')
    overview = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')

    assert 'resource_detail_modal.inventory_host(' in index
    assert 'resource_detail_modal.detail_button(' in overview
    assert 'side_drawer' not in overview
    assert 'openDrawer' not in overview
    assert 'data-kaori-inventory-detail="v10"' in detail
    assert 'Authority Boundary' in detail
    assert 'Provider configuration and live runtime health remain integration-owned.' in detail
    assert 'system.guidance.title' in detail


def test_overview_final_lock_avoids_new_page_local_style_debt() -> None:
    templates = [
        read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html'),
        read('app/templates/storage/object_storage/inventory/overview/partials/_fleet_posture.html'),
        read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot.html'),
        read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html'),
    ]
    source = '\n'.join(templates)
    assert 'text-[' not in source
    assert 'tracking-[' not in source
    assert 'rounded-[2' not in source
