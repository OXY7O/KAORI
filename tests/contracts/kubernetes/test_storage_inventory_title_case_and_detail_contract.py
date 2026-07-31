from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / 'app/templates/inventory/storage/partials/_summary_cards.html'
TABLE = ROOT / 'app/templates/inventory/storage/partials/_table_content.html'
DETAIL = ROOT / 'app/templates/inventory/storage/partials/_storage_detail_content.html'
SERVICE = ROOT / 'app/inventory/resources/storage.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_storage_inventory_uses_canonical_resource_page_pattern() -> None:
    summary = read(SUMMARY)
    table = read(TABLE)

    assert 'Storage Lifecycle Posture' in summary
    assert 'posture_grid.render(posture_metrics, columns=3)' in summary
    for column in ('Storage Object', 'Scope', 'Provisioning', 'Capacity & Access', 'Binding & Lifecycle', 'Details'):
        assert column in table
    assert 'table_ui.namespaced_scope_identity(' in table
    assert "endpoint='inventory.storage'" in table
    assert 'hx-target="#storage-inventory-scope"' in table
    assert '>Rows</label>' in table


def test_storage_detail_uses_adaptive_stacks_and_factual_configuration() -> None:
    detail = read(DETAIL)
    service = read(SERVICE)

    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert 'detail.expanded_workspace_shell_classes()' in detail
    assert "detail.detail_card('Storage Identity'" in detail
    assert "detail.detail_card('Capacity & Access'" in detail
    assert "detail.detail_card('Binding & Lifecycle'" in detail
    assert "detail.detail_card('Provisioning Configuration'" in detail
    assert 'related_collection.render(' in detail
    assert 'metadata_collection.render(' in detail
    assert 'Committed Snapshot Boundary' in detail
    assert "item.type == 'StorageClass'" in detail
    assert "return 'Configured', 'normal'" in service
    assert "normalized_storage_class" not in detail
    assert "reclaim_policy_tone" not in detail
    assert "access_mode_tone" not in detail


def test_storage_relationships_are_bounded_and_use_current_generation() -> None:
    service = read(SERVICE)
    assert 'filter_current_generation' in service
    assert '.limit(8)' in service
    assert 'cast(PodInventory.persistent_volume_claims, JSONB).contains([name])' in service
    assert "'pods_truncated': pods_truncated" in service
    assert "'claims_truncated': claims_truncated" in service
