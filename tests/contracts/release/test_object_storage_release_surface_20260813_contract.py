from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_inventory_has_explicit_release_surface_ownership() -> None:
    registry = read('scripts/release_surface_registry.py')
    assert "key='object_storage_inventory'" in registry
    assert "navigation_source='app/templates/components/navigation/object_storage_menu.html'" in registry
    assert "'object_storage_inventory.overview'" in registry
    assert "'object_storage_inventory.systems'" in registry
    assert "'object_storage_inventory.buckets'" in registry
    assert "blueprint_vars=('object_storage_inventory_bp',)" in registry
    assert "verifiers=('scripts/verify_object_storage_inventory_final_lock.py',)" in registry


def test_release_gate_executes_object_storage_final_lock() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    assert 'python scripts/verify_object_storage_inventory_final_lock.py' in quality_gate


def test_object_storage_release_verifier_locks_committed_snapshot_boundary() -> None:
    verifier = read('scripts/verify_object_storage_inventory_final_lock.py')
    assert 'Object Storage Inventory Final Lock' in verifier
    assert 'Committed Snapshot' in verifier
    assert 'Object Storage inventory routes must not query the live MinIO provider' in verifier
    assert "job_key='object_storage.inventory.sync'" in verifier
