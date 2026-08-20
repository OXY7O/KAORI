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


def test_all_inventory_tables_use_full_workspace_modal_action() -> None:
    component = read('app/templates/components/resource_detail_modal.html')
    script = read('app/static/js/detail_rows.js')

    assert 'macro detail_button(' in component
    assert 'data-resource-detail-toggle' in component
    assert '>View Details<' in component
    assert 'macro host(resource_type, detail_url_template,' in component
    assert "footer_text='Details come from the latest committed inventory snapshot.'" in component
    assert "context_label='Inventory'" in component
    assert "dialog_max_width='max-w-[100rem]'" in component
    assert 'content_driven=false' in component
    assert 'role="dialog"' in component
    assert 'aria-modal="true"' in component
    assert 'max-w-[100rem]' in component
    assert 'data-resource-detail-summary-host' in component
    assert "const DETAIL_PARAM = 'detail'" in script
    assert 'history.pushState' in script
    assert "window.addEventListener('popstate'" in script
    assert "event.key === 'Escape'" in script
    assert 'focusableElements(dialog)' in script

    for resource in RESOURCES:
        table = read(f'app/templates/kubernetes/inventory/{resource}/partials/_table_content.html')
        index = read(f'app/templates/kubernetes/inventory/{resource}/index.html')
        assert 'resource_detail_modal.detail_button(' in table, resource
        assert 'expandable.detail_row(' not in table, resource
        assert 'resource_detail_modal.inventory_host(' in index, resource


def test_all_inventory_detail_workspaces_use_modal_extractable_header_and_summary() -> None:
    detail_component = read('app/templates/components/details/_detail_content.html')
    assert 'data-resource-detail-summary' in detail_component

    for resource, filename in DETAIL_FILES.items():
        source = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        assert 'data-kaori-detail-variant="full-workspace-modal"' in source, resource
        assert 'detail.workspace_header(' in source, resource
        if resource == 'nodes':
            assert 'data-kaori-inventory-detail="v8"' in source
            assert 'data-kaori-inventory-detail-layout="balanced-inspector"' in source
        else:
            assert 'data-kaori-inventory-detail="v6"' in source, resource
        assert 'detail.expanded_workspace_outer_classes()' in source, resource
        assert 'detail.expanded_workspace_shell_classes()' in source, resource


def test_full_workspace_modal_headers_share_grouped_identity_state_geometry() -> None:
    templates = (
        'app/templates/access/activity_audit/partials/_activity_detail.html',
        'app/templates/access/permissions/partials/_permission_detail.html',
        'app/templates/access/roles/partials/_role_detail.html',
        'app/templates/kubernetes/governance/tls_certificates/partials/_detail_content.html',
        'app/templates/kubernetes/inventory/configuration/partials/_configuration_detail_content.html',
        'app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html',
        'app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html',
        'app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html',
        'app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html',
        'app/templates/kubernetes/inventory/services/partials/_service_detail_content.html',
        'app/templates/kubernetes/inventory/storage/partials/_storage_detail_content.html',
        'app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html',
        'app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html',
        'app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html',
    )
    inventory_templates = {relative for relative in templates if '/kubernetes/inventory/' in relative}
    for relative in templates:
        source = read(relative)
        if relative in inventory_templates:
            assert 'workspace_header(' in source, relative
            assert 'header_identity_row()' in source, relative
            assert 'inventory_title(' in source, relative
        else:
            assert 'header_identity_row()' in source, relative
        assert 'header_badge_row()' not in source, relative
