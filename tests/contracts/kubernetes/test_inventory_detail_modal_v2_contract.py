from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESOURCES = ('nodes', 'namespaces', 'workloads', 'pods', 'services', 'ingresses', 'storage', 'configuration')
DETAIL_FILES = {
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


def test_inventory_view_details_use_v2_modal_host_and_shared_resource_header() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'macro inventory_host(' in modal
    assert "'max-w-[90rem]'" in modal
    assert 'Committed Inventory snapshot · No live Kubernetes API query.' in modal
    assert 'backdrop-blur-md' in modal
    assert 'text-lg font-semibold leading-7 text-content-primary' in modal
    assert 'macro workspace_header(' in shared
    assert 'data-resource-detail-header' in shared
    assert 'text-lg font-semibold leading-7 text-content-primary' in shared

    for resource in RESOURCES:
        index = read(f'app/templates/kubernetes/inventory/{resource}/index.html')
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{DETAIL_FILES[resource]}')
        assert 'resource_detail_modal.inventory_host(' in index, resource
        assert 'data-kaori-inventory-detail="v2"' in detail, resource
        assert 'detail.workspace_header(' in detail, resource
        assert '<header data-resource-detail-header' not in detail, resource


def test_inventory_detail_typography_has_one_predictable_hierarchy() -> None:
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')
    technical = read('app/templates/components/technical_value.html')

    # Resource title -> section title -> factual value -> field/supporting label.
    assert 'text-lg font-semibold leading-7 text-content-primary' in shared
    assert 'text-sm font-semibold leading-5 text-content-primary' in shared
    assert 'text-left text-sm font-semibold leading-5 text-content-primary' in shared
    assert 'text-xs font-medium leading-5 text-content-muted' in shared
    assert "size='body'" in shared
    assert "'text-sm leading-5' if size == 'body'" in technical

    # Metadata key/value pairs follow the same label/value hierarchy instead of reversing emphasis.
    assert 'text-xs font-medium leading-5 text-content-muted' in metadata
    assert 'text-sm font-semibold leading-5 text-content-primary' in metadata

    for resource, filename in DETAIL_FILES.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        assert 'text-[10px]' not in detail, resource
        assert 'text-[11px]' not in detail, resource
        assert 'font-mono' not in detail, resource


def test_modal_loading_header_matches_loaded_inventory_header_scale() -> None:
    script = read('app/static/js/detail_rows.js')

    assert 'text-lg font-semibold leading-7 text-content-primary' in script
    assert 'text-sm leading-6 text-content-muted' in script
    assert 'Committed Snapshot' in script
    assert 'border border-brand-outline bg-kaori-soft' in script
