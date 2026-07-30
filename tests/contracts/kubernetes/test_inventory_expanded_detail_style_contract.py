from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESOURCES = ('nodes', 'namespaces', 'workloads', 'pods', 'services', 'ingresses', 'storage', 'configuration')


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_all_inventory_tables_use_shared_view_details_toggle() -> None:
    component = read('app/templates/components/details/_expandable_row.html')
    script = read('app/static/js/detail_rows.js')

    assert "open_label='View Details'" in component
    assert "close_label='Close Details'" in component
    assert 'data-detail-state="closed"' in component
    assert 'data-detail-chevron' in component
    assert 'bg-kaori-mist/40' in component
    assert "button.dataset.detailOpenLabel || 'View Details'" in script
    assert "button.dataset.detailCloseLabel || 'Close Details'" in script
    assert 'Loading Inventory Details' in script

    for resource in RESOURCES:
        table = read(f'app/templates/inventory/{resource}/partials/_table_content.html')
        assert 'expandable.toggle_button(' in table, resource
        assert 'expandable.detail_row(' in table, resource


def test_all_inventory_detail_workspaces_use_shared_expanded_shell() -> None:
    detail_component = read('app/templates/components/details/_detail_content.html')
    assert 'macro expanded_workspace_outer_classes()' in detail_component
    assert 'macro expanded_workspace_shell_classes()' in detail_component
    assert 'macro expanded_workspace_header_classes()' in detail_component

    detail_files = {
        'nodes': '_node_detail_content.html',
        'namespaces': '_namespace_detail_content.html',
        'workloads': '_workload_detail_content.html',
        'pods': '_pod_detail_content.html',
        'services': '_service_detail_content.html',
        'ingresses': '_ingress_detail_content.html',
        'storage': '_storage_detail_content.html',
        'configuration': '_configuration_detail_content.html',
    }
    for resource, filename in detail_files.items():
        source = read(f'app/templates/inventory/{resource}/partials/{filename}')
        assert 'detail.expanded_workspace_outer_classes()' in source, resource
        assert 'detail.expanded_workspace_shell_classes()' in source, resource
        assert 'detail.expanded_workspace_header_classes()' in source, resource
