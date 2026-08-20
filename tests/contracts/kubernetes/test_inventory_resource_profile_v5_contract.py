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


def test_inventory_v5_modal_is_bounded_and_content_driven() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')
    assert "'max-w-[78rem]'" in modal
    assert "'modal', true" in modal
    assert 'text-xl font-semibold leading-7 text-content-primary' in modal


def test_inventory_v5_uses_one_resource_profile_contract_for_all_resources() -> None:
    for resource, filename in DETAILS.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        assert 'data-kaori-detail-density="resource-profile"' in detail, resource
        assert 'data-kaori-inventory-detail="v5"' in detail, resource
        assert 'data-kaori-inventory-detail-layout="resource-profile"' in detail, resource
        assert 'detail.workspace_header(' in detail, resource
        assert 'detail.header_identity_row()' in detail, resource
        assert 'detail.inventory_title(' in detail, resource
        assert 'detail.inventory_section(' in detail, resource


def test_inventory_v5_typography_and_section_geometry_are_consistent() -> None:
    shared = read('app/templates/components/details/_detail_content.html')
    assert 'text-xl font-semibold leading-7 text-content-primary' in shared
    assert 'text-base font-semibold leading-6 text-content-primary' in shared
    assert 'text-sm font-semibold leading-5 text-content-primary' in shared
    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in shared
    assert 'px-4 py-3 sm:px-5' in shared
    assert 'bg-surface-elevated/60' in shared


def test_node_profile_uses_independent_column_stacks_and_reduces_redundant_callouts() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    assert 'grid items-start gap-5 lg:grid-cols-2' in node
    assert node.count('<div class="space-y-5">') == 2
    assert "detail.inventory_section('Node Identity'" in node
    assert "detail.inventory_section('Node Capacity'" in node
    assert "detail.inventory_section('Connectivity'" in node
    assert "detail.inventory_section('Platform & Runtime'" in node
    assert "detail.inventory_section('Scheduling & Conditions'" in node
    assert "operational_callout.render('Committed Snapshot Boundary'" not in node


def test_large_metadata_collections_are_contained_and_scannable() -> None:
    metadata = read('app/templates/components/technical_metadata_collection.html')
    related = read('app/templates/components/related_resource_collection.html')
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in metadata
    assert 'max-h-[24rem] overflow-y-auto' in metadata
    assert 'grid min-w-0 gap-x-5 sm:grid-cols-2 xl:grid-cols-3' in metadata
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in related
    assert 'divide-y divide-outline-subtle px-4 sm:px-5' in related
