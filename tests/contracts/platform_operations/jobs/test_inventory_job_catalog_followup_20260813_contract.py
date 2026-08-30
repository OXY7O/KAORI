from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_job_catalog_uses_page_scroll_instead_of_nested_scroll() -> None:
    workspace = read('app/templates/platform_operations/jobs/configuration/_workspace.html')

    assert 'max-h-[620px]' not in workspace
    assert 'overflow-y-auto' not in workspace
    assert '<div class="space-y-3">' in workspace


def test_kubernetes_inventory_job_is_named_explicitly() -> None:
    labels = read('app/common/job_execution_contract.py')
    job_catalog = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    template = read('app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html')
    configuration = read('app/platform_operations/jobs/configuration.py')

    assert "KUBERNETES_INVENTORY_SYNC_OPERATION = 'sync_kubernetes_inventory'" in labels
    assert 'operation: sync_kubernetes_inventory' in job_catalog
    assert 'name: Kubernetes Inventory Sync' in job_catalog
    assert 'Kubernetes Inventory Sync Policy' in template
    assert 'Automatic Kubernetes Inventory Sync' in template
    assert "'manual_action_label': 'Sync Kubernetes Inventory'" in configuration


def test_quick_sync_all_inventory_dispatches_all_authorized_inventory_domains() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')
    routes = read('app/platform_operations/jobs/routes.py')

    assert "url_for('jobs.quick_sync_all_inventory')" in navbar
    assert 'Sync All Inventory' in navbar
    assert "can_sync_kubernetes_inventory = current_user.has_permission('clusters.sync')" in navbar
    assert "can_sync_object_storage_inventory = current_user.has_permission('storage.sync')" in navbar
    assert 'every eligible managed domain' in navbar
    assert "@bp.post('/quick-actions/inventory/sync-all')" in routes
    assert "job_keys.append('kubernetes.inventory.sync')" in routes
    assert "job_keys.append('object_storage.inventory.sync')" in routes
    assert "current_user.has_permission('clusters.sync')" in routes
    assert "current_user.has_permission('storage.sync')" in routes
    assert "queue='inventory'" in routes
