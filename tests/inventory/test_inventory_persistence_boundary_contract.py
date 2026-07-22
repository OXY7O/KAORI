from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_service_is_a_public_facade_for_persistence_and_sync():
    source = (ROOT / 'app/inventory/service.py').read_text(encoding='utf-8')
    assert 'from app.inventory.persistence import (' in source
    assert 'from app.inventory.synchronization import sync_inventory' in source
    assert 'def save_nodes(' not in source
    assert 'def sync_inventory(' not in source


def test_inventory_persistence_owns_replacement_writes():
    source = (ROOT / 'app/inventory/persistence.py').read_text(encoding='utf-8')
    for function_name in (
        'save_cluster_info', 'save_nodes', 'save_namespaces', 'save_workloads',
        'save_pods', 'save_services', 'save_ingresses', 'save_storage_inventory',
        'save_configuration_inventory', 'save_resource_quotas',
    ):
        assert f'def {function_name}(' in source
    assert 'def sync_inventory(' not in source


def test_inventory_synchronization_owns_transaction_orchestration():
    source = (ROOT / 'app/inventory/synchronization.py').read_text(encoding='utf-8')
    assert 'def _lock_cluster_inventory_sync(' in source
    assert 'def sync_inventory(' in source
    assert "current_stage = 'cluster lock'" in source
    assert 'db.session.commit()' in source
    assert 'db.session.rollback()' in source


def test_inventory_persistence_and_sync_do_not_import_service_facade():
    for relative in (
        'app/inventory/persistence.py',
        'app/inventory/synchronization.py',
    ):
        source = (ROOT / relative).read_text(encoding='utf-8')
        assert 'from app.inventory.service' not in source
        assert 'import app.inventory.service' not in source
