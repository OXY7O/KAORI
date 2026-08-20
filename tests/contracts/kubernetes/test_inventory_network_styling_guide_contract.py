from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_service_and_ingress_use_shared_network_inventory_contracts() -> None:
    service_detail = read('app/templates/kubernetes/inventory/services/partials/_service_detail_content.html')
    ingress_detail = read('app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html')
    pattern = read('docs/design/patterns/KUBERNETES_NETWORK_INVENTORY.md')

    for source in (service_detail, ingress_detail):
        assert 'data-kaori-detail-density="resource-profile"' in source
        assert 'detail.expanded_workspace_shell_classes()' in source
        assert 'technical_metadata_collection.html' in source
        assert 'related_resource_collection.html' in source
        assert 'Operational Context' in source
        assert 'Committed Snapshot Boundary' in source

    assert 'EndpointSlice' in pattern
    assert 'No TLS reference remains neutral' in pattern
    assert 'Service | Scope | Access Model | Port Mapping | Backend Registration | Details' in pattern
    assert 'Ingress | Scope | Publication | TLS References | Routing | Details' in pattern


def test_inventory_fact_grid_uses_one_grouped_boundary_without_floating_tiles() -> None:
    detail = read('app/templates/components/details/_detail_content.html')

    assert 'macro inventory_fact_grid(rows, columns=2)' in detail
    assert 'data-kaori-inventory-fact-grid' in detail
    assert 'data-kaori-inventory-fact-grid' in detail
    assert 'rounded-lg border border-outline-subtle bg-surface-card' not in detail.split('{% macro inventory_fact_grid', 1)[1].split('{%- endmacro %}', 1)[0]
    assert 'overflow-hidden rounded-lg border border-outline-subtle bg-surface-elevated' in detail


def test_metadata_collection_avoids_nested_vertical_scroll() -> None:
    metadata = read('app/templates/components/technical_metadata_collection.html')
    pod_detail = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')

    assert 'max-h-56 overflow-y-auto' not in metadata
    assert 'data-kaori-inventory-metadata-collection' in metadata
    assert 'max-h-56 overflow-y-auto' not in metadata
    assert 'grid items-start gap-4 lg:grid-cols-2' in pod_detail


def test_volume_source_uses_body_typography() -> None:
    pod_detail = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')
    technical = read('app/templates/components/technical_value.html')

    assert (
        "technical_value.render(volume.source, break_all=true, class_name='font-medium', size='body')" in pod_detail
    )
    assert "size='compact'" in technical
    assert "'text-sm leading-5' if size == 'body'" in technical


def test_node_scheduling_and_namespace_security_use_available_space() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    namespace = read('app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html')

    assert 'columns=5' in node
    assert 'Scheduling Taints' in node
    assert 'Control Interpretation' in namespace
    assert 'Default ServiceAccount presence is shown separately' in namespace
