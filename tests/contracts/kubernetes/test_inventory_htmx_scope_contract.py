from pathlib import Path

RESOURCE_NAMES = (
    'nodes',
    'namespaces',
    'configuration',
    'workloads',
    'pods',
    'services',
    'ingresses',
    'storage',
)


def test_filter_requests_replace_summary_and_table_as_one_scope() -> None:
    for resource in RESOURCE_NAMES:
        index = Path(f'app/templates/inventory/{resource}/index.html').read_text()
        scope = Path(f'app/templates/inventory/{resource}/partials/_inventory_scope.html').read_text()
        card = Path(f'app/templates/inventory/{resource}/partials/_table_card.html').read_text()

        assert f'inventory/{resource}/partials/_inventory_scope.html' in index
        assert f'id="{resource}-inventory-scope"' in scope
        assert f'inventory/{resource}/partials/_summary_cards.html' in scope
        assert f'inventory/{resource}/partials/_table_card.html' in scope
        assert f'hx-target="#{resource}-inventory-scope"' in card
        assert 'name="partial_mode" value="inventory_scope"' in card

        content = Path(f'app/templates/inventory/{resource}/partials/_table_content.html').read_text()
        assert f'hx-target="#{resource}-table-content"' in content


def test_routes_share_one_htmx_partial_selector() -> None:
    source = Path('app/inventory/routes.py').read_text()

    assert 'def _inventory_template(resource: str) -> str:' in source
    assert "partial_mode == 'table_content'" in source
    assert "partial_mode == 'inventory_scope'" in source
    for resource in RESOURCE_NAMES:
        assert f"_inventory_template('{resource}')" in source


def test_workload_details_do_not_infer_configuration_from_runtime_pods() -> None:
    service = Path('app/inventory/resources/workloads.py').read_text()
    template = Path('app/templates/inventory/workloads/partials/_workload_detail_content.html').read_text()

    assert 'associated-pod-fallback' not in service
    assert 'associated-pod-fallback' not in template
    assert "pod_template.get('reported') is True" in service


def test_inventory_sync_uses_structured_logging() -> None:
    source = Path('app/inventory/synchronization.py').read_text()

    assert 'logger.exception(' in source
    assert "print('=== INVENTORY SYNC EXCEPTION ===')" not in source


RESOURCE_SERVICE_FUNCTIONS = {
    'nodes.py': 'get_node_inventory',
    'namespaces.py': 'get_namespace_inventory',
    'configuration.py': 'get_configuration_inventory_view',
    'workloads.py': 'get_workload_inventory',
    'pods.py': 'get_pod_inventory',
    'services.py': 'get_service_inventory',
    'ingresses.py': 'get_ingress_inventory',
    'storage.py': 'get_storage_inventory_view',
}


def test_resource_lists_use_canonical_server_side_pagination() -> None:
    route_source = Path('app/inventory/routes.py').read_text()

    for filename, function_name in RESOURCE_SERVICE_FUNCTIONS.items():
        service_source = Path('app/inventory/resources', filename).read_text()
        assert 'from app.common.pagination import paginate_query' in service_source
        assert f'def {function_name}(' in service_source
        assert 'paginate_query(' in service_source

    for resource in RESOURCE_NAMES:
        route_start = route_source.index(f'def {resource}():')
        next_route = route_source.find('@inventory_bp.', route_start)
        route_segment = route_source[route_start : next_route if next_route >= 0 else None]
        assert 'page=page' in route_segment
        assert 'per_page=per_page' in route_segment
        assert "pagination=inventory['pagination']" in route_segment
        assert 'paginate_sequence(' not in route_segment
