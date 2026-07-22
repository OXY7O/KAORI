from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_retired_inventory_service_facade_is_absent() -> None:
    assert not (ROOT / 'app/inventory/service.py').exists()


def test_inventory_persistence_owns_replacement_writes() -> None:
    source = (ROOT / 'app/inventory/persistence.py').read_text(encoding='utf-8')
    for function_name in (
        'save_cluster_info', 'save_nodes', 'save_namespaces', 'save_workloads',
        'save_pods', 'save_services', 'save_ingresses', 'save_storage_inventory',
        'save_configuration_inventory', 'save_resource_quotas',
    ):
        assert f'def {function_name}(' in source
    assert 'def sync_inventory(' not in source


def test_inventory_synchronization_owns_transaction_orchestration() -> None:
    source = (ROOT / 'app/inventory/synchronization.py').read_text(encoding='utf-8')
    assert 'def _lock_cluster_inventory_sync(' in source
    assert 'def sync_inventory(' in source
    assert "current_stage = 'cluster lock'" in source
    assert 'db.session.commit()' in source
    assert 'db.session.rollback()' in source


def test_runtime_adapter_calls_synchronization_owner_directly() -> None:
    source = (ROOT / 'app/integrations/kubernetes/adapter.py').read_text(encoding='utf-8')
    assert 'from app.inventory.synchronization import sync_inventory' in source
    assert 'from app.inventory.service' not in source
