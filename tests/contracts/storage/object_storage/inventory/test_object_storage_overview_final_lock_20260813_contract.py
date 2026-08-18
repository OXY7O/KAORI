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


def test_overview_system_drawer_matches_systems_final_authority_boundary() -> None:
    overview = read('app/templates/storage/object_storage/inventory/overview/partials/_systems_snapshot_content.html')

    assert "width='2xl'" in overview
    assert 'x_show="openDrawer === \'" ~ system.id ~ "\'"' in overview
    assert "x_show='openDrawer === ' ~ (system.id|tojson)" not in overview
    assert 'System Snapshot Summary' in overview
    assert 'Operational Reading' in overview
    assert 'Authority Boundary' in overview
    assert 'Related Operational Workspace' in overview
    assert 'Provider configuration, validation, and runtime health remain integration-owned.' in overview
    assert "job_key='object_storage.inventory.sync'" in overview


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
