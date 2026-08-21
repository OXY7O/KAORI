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


def test_inventory_v6_modal_is_bounded_and_content_driven() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')
    assert "'max-w-[92rem]'" in modal
    assert "'modal', true" in modal
    assert 'text-xl font-semibold leading-7 text-content-primary' in modal


def test_inventory_v6_uses_one_horizontal_section_contract_for_all_resources() -> None:
    for resource, filename in DETAILS.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        if resource == 'nodes':
            assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
            assert 'data-kaori-inventory-detail="v10"' in detail
            assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail
            assert 'detail.inspector_section(' in detail
        else:
            assert 'data-kaori-detail-density="unified-resource-sheet"' in detail, resource
            assert 'data-kaori-inventory-detail="v10"' in detail, resource
            assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail, resource
            assert 'detail.inventory_section(' in detail, resource
        assert 'detail.workspace_header(' in detail, resource
        assert 'detail.header_identity_row()' in detail, resource
        assert 'detail.inventory_title(' in detail, resource


def test_inventory_v6_typography_and_section_geometry_are_consistent() -> None:
    shared = read('app/templates/components/details/_detail_content.html')
    assert 'text-xl font-semibold leading-7 text-content-primary' in shared
    assert 'text-base font-semibold leading-6 text-content-primary' in shared
    assert 'text-sm font-semibold leading-5 text-content-primary' in shared
    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert 'data-kaori-inventory-section-layout="resource-sheet-band"' in shared
    assert 'xl:grid-cols-[17rem_minmax(0,1fr)]' in shared
    assert 'bg-surface-elevated/35' in shared
    assert 'mt-3 flex min-w-0 items-start gap-2 border-t border-outline-subtle pt-3' in shared
    assert 'data-kaori-inventory-section-description' in shared
    assert 'absolute inset-y-0 left-0 w-0.5 bg-kaori-primary/70' in shared


def test_node_profile_uses_unified_resource_sheet_and_preserves_snapshot_boundary() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-node-inspector' in node
    assert 'data-kaori-node-inspector-flow="natural-content"' in node
    assert 'data-kaori-node-inspector-layout="single-scroll-resource-sheet"' in node
    assert 'data-kaori-node-resource-sheet' in node
    assert 'data-kaori-inspector-section-layout="resource-sheet-band"' in shared
    assert "detail.inspector_section('Identity & Snapshot'" in node
    assert "detail.inspector_section('Node Capacity'" in node
    assert "detail.inspector_section('Connectivity & Network'" in node
    assert "detail.inspector_section('Runtime & Platform'" in node
    assert "detail.inspector_section('Scheduling & Conditions'" in node
    assert "operational_callout.render('Committed Snapshot Boundary'" in node


def test_large_metadata_collections_are_contained_and_scannable() -> None:
    metadata = read('app/templates/components/technical_metadata_collection.html')
    related = read('app/templates/components/related_resource_collection.html')
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in metadata
    assert 'overflow-y-auto' not in metadata
    assert "special_label(entry_count_label, 'maintenance', 'tags', 'detail')" in metadata
    assert 'grid min-w-0 gap-x-6 sm:grid-cols-2 xl:grid-cols-3' in metadata
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in related
    assert 'divide-y divide-outline-subtle px-4 sm:px-5' in related
