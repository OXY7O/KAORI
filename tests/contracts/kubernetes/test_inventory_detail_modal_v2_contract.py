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


def test_inventory_view_details_use_v5_resource_profile_host_and_shared_resource_header() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'macro inventory_host(' in modal
    assert "'max-w-[78rem]'" in modal
    assert "'modal', true" in modal
    assert 'Committed Inventory snapshot · No live Kubernetes API query.' in modal
    assert 'backdrop-blur-md' in modal
    assert 'text-xl font-semibold leading-7 text-content-primary' in modal
    assert 'macro workspace_header(' in shared
    assert 'macro header_identity_row()' in shared
    assert 'macro inventory_title(' in shared
    assert 'macro inventory_section(' in shared
    assert 'macro inventory_row(' in shared
    assert 'macro inventory_technical_row(' in shared
    assert 'macro inventory_fact_grid(' in shared
    assert 'data-resource-detail-header' in shared
    assert 'data-resource-detail-header-identity' in shared
    assert 'data-kaori-inventory-detail-section' in shared
    assert 'data-kaori-inventory-fact-grid' in shared
    assert 'text-xl font-semibold leading-7 text-content-primary' in shared

    for resource in RESOURCES:
        index = read(f'app/templates/kubernetes/inventory/{resource}/index.html')
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{DETAIL_FILES[resource]}')
        assert 'resource_detail_modal.inventory_host(' in index, resource
        assert 'data-kaori-inventory-detail="v5"' in detail, resource
        assert 'data-kaori-inventory-detail-layout="resource-profile"' in detail, resource
        assert 'detail.workspace_header(' in detail, resource
        assert 'detail.header_identity_row()' in detail, resource
        assert 'detail.inventory_title(' in detail, resource
        assert 'detail.inventory_section(' in detail, resource
        assert 'detail.inventory_fact_grid(' in detail, resource
        assert '<header data-resource-detail-header' not in detail, resource


def test_inventory_detail_typography_has_one_predictable_hierarchy() -> None:
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')
    technical = read('app/templates/components/technical_value.html')
    runtime = read('app/templates/components/container_runtime_collection.html')

    # Resource title -> summary value -> section title -> one body scale for field label/value -> supporting copy.
    assert 'text-xl font-semibold leading-7 text-content-primary' in shared
    assert 'text-base font-semibold leading-6 text-content-primary' in shared
    assert 'text-sm font-semibold leading-5 text-content-primary' in shared
    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert "size='body'" in shared
    assert "'text-sm leading-5' if size == 'body'" in technical
    assert (
        "technical_value.render(container.image or 'Not Reported', break_all=true, class_name='font-medium', size='body')"
        in runtime
    )
    assert 'text-sm font-semibold tabular-nums text-content-primary' in runtime

    # Metadata key/value pairs use the same 14px body scale and differ by tone rather than size.
    assert 'text-sm font-normal leading-5 text-content-secondary' in metadata
    assert 'text-sm font-medium leading-5 text-content-primary' in metadata

    for resource, filename in DETAIL_FILES.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        assert 'text-[10px]' not in detail, resource
        assert 'text-[11px]' not in detail, resource
        assert 'font-mono' not in detail, resource


def test_modal_loading_header_matches_loaded_inventory_header_scale() -> None:
    script = read('app/static/js/detail_rows.js')

    assert 'text-xl font-semibold leading-7 text-content-primary' in script
    assert 'text-sm leading-6 text-content-muted' in script
    assert 'Committed Snapshot' in script
    assert 'ring-1 ring-inset ring-brand-outline/60' in script


def test_configuration_key_inventory_uses_full_width_grouped_list_instead_of_tile_wall() -> None:
    configuration = read('app/templates/kubernetes/inventory/configuration/partials/_configuration_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')

    assert 'space-y-5 p-4 sm:p-5 lg:p-6' in configuration
    assert "metadata_collection.render('Key Inventory'" in configuration
    assert (
        'grid min-w-0 gap-x-8 sm:grid-cols-2 xl:grid-cols-3'
        in metadata
    )
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated px-3 py-2.5' not in metadata
    assert 'data-kaori-inventory-metadata-collection' in metadata
