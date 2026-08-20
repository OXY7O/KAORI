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


def test_inventory_v4_is_a_fact_sheet_not_a_nested_card_gallery() -> None:
    shared = read('app/templates/components/details/_detail_content.html')

    section = shared.split('{% macro inventory_section', 1)[1].split('{%- endmacro %}', 1)[0]
    assert 'rounded-xl border border-outline-subtle bg-surface-card' not in section
    assert 'border-b border-outline-subtle pb-2.5' in section
    assert 'text-sm font-normal leading-5 text-content-muted' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert 'macro inventory_note(' in shared
    assert 'grid min-w-0 gap-x-6' in shared

    for resource, filename in DETAILS.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        assert 'data-kaori-inventory-detail="v4"' in detail, resource
        assert 'data-kaori-inventory-detail-layout="operational-fact-sheet"' in detail, resource


def test_node_detail_uses_inline_guidance_and_open_evidence_columns() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert 'components/detail_tip.html' not in node
    assert node.count('detail.inventory_note(') == 3
    assert 'grid items-start gap-x-10 gap-y-8 p-5 sm:p-6 xl:grid-cols-2' in node
    assert "detail.inventory_section('Node Identity'" in node
    assert "detail.inventory_section('Node Capacity'" in node
    assert "detail.inventory_section('Connectivity'" in node
    assert "detail.inventory_section('Platform & Runtime'" in node


def test_metadata_collections_use_flat_rows_and_no_tile_wall() -> None:
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'data-kaori-inventory-metadata-collection' in metadata
    assert 'grid min-w-0 gap-x-8 sm:grid-cols-2 xl:grid-cols-3' in metadata
    assert 'border-b border-outline-subtle py-2.5' in metadata
    assert 'gap-px overflow-hidden rounded-lg border border-outline-subtle bg-outline-subtle' not in metadata
    assert 'bg-surface-card px-3 py-2.5' not in metadata


def test_inventory_related_resources_use_flat_collection_variant() -> None:
    related = read('app/templates/components/related_resource_collection.html')
    assert 'macro inventory_render(' in related
    assert 'data-kaori-inventory-related-collection' in related
    assert 'border-b border-outline-subtle pb-2.5' in related

    for resource in ('workloads', 'pods', 'services', 'ingresses', 'storage', 'configuration'):
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{DETAILS[resource]}')
        if 'related_resource_collection.html' in detail:
            assert 'related_collection.inventory_render(' in detail, resource
