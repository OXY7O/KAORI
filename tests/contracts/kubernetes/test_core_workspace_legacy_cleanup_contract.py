from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_reviewed_core_workspaces_do_not_restore_internal_compatibility_bridges() -> None:
    obsolete = (
        'app/static/js/inventory/topology_bootstrap.js',
        'app/templates/inventory/components/_detail_macros.html',
        'app/templates/inventory/nodes/partials/_inventory_scope.html',
        'app/templates/inventory/namespaces/partials/_inventory_scope.html',
        'app/templates/inventory/workloads/partials/_inventory_scope.html',
        'app/templates/inventory/pods/partials/_inventory_scope.html',
        'app/templates/inventory/services/partials/_inventory_scope.html',
        'app/templates/inventory/ingresses/partials/_inventory_scope.html',
        'app/templates/inventory/storage/partials/_inventory_scope.html',
    )
    assert all(not (ROOT / relative).exists() for relative in obsolete)

    welcome_routes = read('app/welcome/routes.py')
    assert "@welcome_bp.route('/')" in welcome_routes
    assert "@welcome_bp.route('/welcome')" in welcome_routes
    assert 'redirect(' not in welcome_routes

    dashboard_repository = read('app/dashboards/kubernetes/repository.py')
    assert 'load_models' not in dashboard_repository
    assert 'import_module' not in dashboard_repository
    assert 'filter_current_generation(query, model)' in dashboard_repository

    overview_route = read('app/inventory/routes.py')
    overview_content = read('app/templates/inventory/overview/partials/_resources_by_cluster_content.html')
    assert "'inventory/overview/partials/_resources_by_cluster_content.html'" in overview_route
    assert 'hx-target="#resources-by-cluster-content"' in overview_content

    topology_index = read('app/templates/inventory/topology/index.html')
    topology_script = read('app/static/js/inventory/topology.js')
    assert "filename='js/inventory/topology.js'" in topology_index
    assert 'await import(config.renderer_url)' in topology_script
    assert 'window.cytoscape' not in topology_script

    topology_service = read('app/inventory/topology/service.py')
    assert '_node_element' not in topology_service
    assert 'TopologyGraphBuilder' in topology_service
    assert (ROOT / 'app/inventory/topology/repository.py').exists()
    assert (ROOT / 'app/inventory/topology/node_builder.py').exists()
    assert (ROOT / 'app/inventory/topology/edge_builder.py').exists()


def test_reviewed_inventory_resources_use_canonical_workspace_and_table_boundaries() -> None:
    for resource in ('nodes', 'namespaces', 'workloads', 'pods', 'services', 'ingresses', 'storage'):
        workspace = read(f'app/templates/inventory/{resource}/partials/_page_workspace.html')
        table = read(f'app/templates/inventory/{resource}/partials/_table_content.html')

        assert f'id="{resource}-page-workspace"' in workspace
        assert f'hx-target="#{resource}-table-content"' in table
        assert 'name="partial_mode" value="table_content"' in table
        assert f'{resource}-inventory-scope' not in workspace
        assert f'{resource}-inventory-scope' not in table


def test_service_inventory_uses_json_evidence_without_duplicate_columns() -> None:
    model = read('app/models/inventory.py')
    service_class = model.split('class ServiceInventory', 1)[1].split('class IngressInventory', 1)[0]
    migration = read('migrations/versions/20260805_service_inventory_v2.py')

    assert 'external_ip:' not in service_class
    assert 'ports:' not in service_class
    assert "op.drop_column('service_inventory', 'ports')" in migration
    assert "op.drop_column('service_inventory', 'external_ip')" in migration


def test_ingress_inventory_uses_json_evidence_without_duplicate_columns() -> None:
    model = read('app/models/inventory.py')
    ingress_class = model.split('class IngressInventory', 1)[1].split('class StorageInventory', 1)[0]
    collector = read('app/inventory/collectors/ingresses.py')
    migration = read('migrations/versions/20260805_ingress_inventory_v2.py')

    assert 'host:' not in ingress_class
    assert 'address:' not in ingress_class
    assert "'namespace': str(namespace),\n                'ingress_name': str(name),\n                'ingress_class': ingress_class,\n                'tls_enabled': bool(tls_entries)" in collector
    assert "op.drop_column('ingress_inventory', 'host')" in migration
    assert "op.drop_column('ingress_inventory', 'address')" in migration
