from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_inventory_operations_use_explicit_domain_names() -> None:
    contract = read('app/common/job_execution_contract.py')
    job_catalog = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')

    assert "KUBERNETES_INVENTORY_SYNC_OPERATION = 'sync_kubernetes_inventory'" in contract
    assert "OBJECT_STORAGE_INVENTORY_SYNC_OPERATION = 'sync_object_storage_inventory'" in contract
    assert "SYNC_ALL_INVENTORY_ACTION = 'sync_all_inventory'" in contract
    assert 'operation: sync_kubernetes_inventory' in job_catalog
    assert 'operation: sync_object_storage_inventory' in job_catalog


def test_inventory_job_keys_remain_stable_while_operations_are_renamed() -> None:
    job_catalog = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')

    assert 'key: kubernetes.inventory.sync' in job_catalog
    assert 'key: object_storage.inventory.sync' in job_catalog


def test_inventory_runtime_queries_use_canonical_operation_constants() -> None:
    kubernetes_adapter = read('app/kubernetes/inventory/job_adapter.py')
    object_storage_adapter = read('app/storage/object_storage/inventory/job_adapter.py')
    kubernetes_sync = read('app/kubernetes/cluster/sync_jobs.py')
    object_storage_sync = read('app/storage/object_storage/inventory/sync_jobs.py')
    deletion = read('app/integrations/deletion.py')
    sync_state = read('app/kubernetes/cluster/sync_state.py')

    assert 'JobExecution.operation == KUBERNETES_INVENTORY_SYNC_OPERATION' in kubernetes_adapter
    assert 'operation=KUBERNETES_INVENTORY_SYNC_OPERATION' in kubernetes_sync
    assert 'JobExecution.operation == OBJECT_STORAGE_INVENTORY_SYNC_OPERATION' in object_storage_adapter
    assert 'operation=OBJECT_STORAGE_INVENTORY_SYNC_OPERATION' in object_storage_sync
    assert 'JobExecution.operation == KUBERNETES_INVENTORY_SYNC_OPERATION' in deletion
    assert 'JobExecution.operation == KUBERNETES_INVENTORY_SYNC_OPERATION' in sync_state


def test_inventory_operation_history_is_migrated_without_changing_job_policy_keys() -> None:
    migration = read('migrations/versions/20260813_inventory_operation_names.py')

    assert "revision = '20260813_inventory_op_names'" in migration
    assert "down_revision = '20260813_obj_storage_jobs'" in migration
    assert "KUBERNETES_OLD = 'inventory_sync_all'" in migration
    assert "KUBERNETES_NEW = 'sync_kubernetes_inventory'" in migration
    assert "OBJECT_STORAGE_OLD = 'object_storage_inventory_sync_all'" in migration
    assert "OBJECT_STORAGE_NEW = 'sync_object_storage_inventory'" in migration
    assert "sa.table(\n        'job_executions'" in migration
    assert "'job_policies'" not in migration


def test_sync_all_inventory_is_a_global_action_not_a_domain_job_operation() -> None:
    routes = read('app/platform_operations/jobs/routes.py')
    contract = read('app/common/job_execution_contract.py')

    assert "SYNC_ALL_INVENTORY_ACTION = 'sync_all_inventory'" in contract
    assert "event_type=f'{SYNC_ALL_INVENTORY_ACTION}_quick_action'" in routes
    assert "'operation': SYNC_ALL_INVENTORY_ACTION" in routes
    assert "job_keys.append('kubernetes.inventory.sync')" in routes
    assert "job_keys.append('object_storage.inventory.sync')" in routes
