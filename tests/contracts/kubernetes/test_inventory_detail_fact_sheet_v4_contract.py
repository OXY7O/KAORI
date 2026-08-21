from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DETAILS = {
    'nodes': '_node_detail_content.html',
    'namespaces': '_namespace_detail_content.html',
    'workloads': '_workload_detail_content.html',
    'pods': '_pod_detail_content.html',
    'services': '_service_detail_content.html',
    'ingresses': '_ingress_detail_content.html',
    'storage': '_storage_detail_content.html',
    'configuration': '_configuration_detail_content.html',
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_v6_uses_horizontal_section_bands_with_natural_height() -> None:
    shared = read('app/templates/components/details/_detail_content.html')
    modal = read('app/templates/components/resource_detail_modal.html')

    section = shared.split('{% macro inventory_section', 1)[1].split('{%- endmacro %}', 1)[0]
    assert 'data-kaori-inventory-section-layout="resource-sheet-band"' in section
    assert 'xl:grid-cols-[20rem_minmax(0,1fr)]' in section
    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert 'macro inventory_note(' in shared
    assert 'data-kaori-inventory-fact-grid' in shared
    assert "'max-w-[92rem]'" in modal

    for resource, filename in DETAILS.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        if resource == 'nodes':
            assert 'data-kaori-inventory-detail="v10"' in detail
            assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail
        else:
            assert 'data-kaori-inventory-detail="v10"' in detail, resource
            assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail, resource


def test_node_detail_uses_balanced_inspector_and_grouped_conditions() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert 'data-kaori-node-inspector' in node
    assert 'data-kaori-node-inspector-flow="natural-content"' in node
    assert 'xl:grid-cols-12' in node
    assert "detail.inspector_section('Identity & Snapshot'" in node
    assert "detail.inspector_section('Node Capacity'" in node
    assert "detail.inspector_section('Connectivity & Network'" in node
    assert "detail.inspector_section('Runtime & Platform'" in node
    assert "detail.inspector_section('Scheduling & Conditions'" in node
    assert "operational_callout.render('Committed Snapshot Boundary'" in node
    assert 'operational_callout.render(node.operational_context.title' in node


def test_metadata_collections_are_contained_lists_not_tile_walls() -> None:
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'data-kaori-inventory-metadata-collection' in metadata
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in metadata
    assert 'overflow-y-auto' not in metadata
    assert "special_label(entry_count_label, 'maintenance', 'tags', 'detail')" in metadata
    assert 'grid min-w-0 gap-x-6 gap-y-0 sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-3' in metadata
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated px-3 py-2.5' not in metadata


def test_inventory_related_resources_use_contained_list_variant() -> None:
    related = read('app/templates/components/related_resource_collection.html')
    assert 'macro inventory_render(' in related
    assert 'data-kaori-inventory-related-collection' in related
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in related
    assert 'divide-y divide-outline-subtle px-4 sm:px-5' in related

    for resource in ('workloads', 'pods', 'services', 'ingresses', 'storage', 'configuration'):
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{DETAILS[resource]}')
        if 'related_resource_collection.html' in detail:
            assert 'related_collection.inventory_render(' in detail, resource
