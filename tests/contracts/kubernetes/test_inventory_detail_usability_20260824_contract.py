from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_resource_sheet_bands_align_with_four_column_summary_header() -> None:
    shared = read('app/templates/components/details/_detail_content.html')
    metadata = read('app/templates/components/technical_metadata_collection.html')
    related = read('app/templates/components/related_resource_collection.html')

    assert 'macro inventory_band_grid_classes()' in shared
    assert 'xl:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]' in shared
    assert 'class="{{ inventory_band_grid_classes() }}"' in shared
    assert 'class="{{ detail.inventory_band_grid_classes() }}"' in metadata
    assert 'class="{{ detail.inventory_band_grid_classes() }}"' in related
    assert 'xl:grid-cols-[20rem_minmax(0,1fr)]' not in shared
    assert 'data-kaori-inventory-summary-alignment="shared-gutter"' in shared
    assert 'mx-4 mt-5' in shared
    assert 'sm:mx-5' in shared
    assert 'lg:mx-6' in shared

    detail_files = {
        'overview': '_cluster_detail_content.html',
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
        source = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        assert 'p-4 sm:p-5 lg:p-6' in source, resource


def test_inventory_copy_controls_are_shared_and_used_for_identifiers_and_addresses() -> None:
    shared = read('app/templates/components/details/_detail_content.html')
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    namespace = read('app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html')
    workload = read('app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html')
    pod = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')
    service = read('app/templates/kubernetes/inventory/services/partials/_service_detail_content.html')
    ingress = read('app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html')
    storage = read('app/templates/kubernetes/inventory/storage/partials/_storage_detail_content.html')
    pod_detail = read('app/kubernetes/inventory/resources/pod_detail.py')

    assert 'macro inventory_copy_button(label)' in shared
    assert 'data-kaori-copy-button' in shared
    assert 'data-kaori-copy-source' in shared
    assert 'data-lucide="copy"' in shared
    assert 'data-kaori-copy-icon' in shared
    assert "inventory_technical_row('UID', namespace.uid, copyable=true)" in namespace
    assert "inventory_technical_row('UID', workload.uid, copyable=true)" in workload
    assert "inventory_technical_row('Kubernetes UID', pod.uid, copyable=true)" in pod
    assert "inventory_technical_row('Kubernetes UID', service.uid, copyable=true)" in service
    assert "inventory_technical_row('Kubernetes UID', ingress.uid, copyable=true)" in ingress
    assert "inventory_technical_row('Kubernetes UID', item.uid, copyable=true)" in storage
    assert "macro inspector_technical_row(label, value='-', nowrap=false, class_name='', copyable=false)" in shared
    assert "inspector_technical_row('System UUID', node.system_uuid" in node
    assert 'copyable=true' in node
    assert "'label': 'Pod IP', 'value': pod.pod_ip or unknown, 'copyable': True" in pod_detail
    assert "'label': 'Host IP', 'value': details.get('host_ip') or unknown, 'copyable': True" in pod_detail
    assert "{'label': 'Cluster IP', 'value': service.cluster_ip, 'copyable': true}" in service


def test_namespace_control_copy_and_reported_quota_presentation_are_concise() -> None:
    detail = read('app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html')

    assert 'Unset namespace controls remain neutral until evaluated against an explicit governance policy.' in detail
    assert 'KAORI does not infer cluster-level Pod Security Admission defaults from missing labels.' in detail
    assert 'Default ServiceAccount presence is reported separately as access-baseline evidence.' in detail
    assert 'Controls that are not explicitly set at namespace level remain neutral evidence' not in detail
    assert 'data-kaori-reported-quota' in detail
    assert 'Configured hard limits' in detail
    assert '>Resource</span>' in detail
    assert '>Hard Limit</span>' in detail
    assert 'divide-y divide-outline-subtle' in detail


def test_inventory_search_copy_is_compact_for_dense_filter_rows() -> None:
    expectations = {
        'pods': "'Name, IP, owner, or node'",
        'ingresses': "'Name, host, backend, or Secret'",
        'storage': "'Object, class, or binding'",
        'configuration': "'Name, type, or namespace'",
    }
    for resource, placeholder in expectations.items():
        source = read(f'app/templates/kubernetes/inventory/{resource}/partials/_table_card.html')
        assert '>Search</label>' in source, resource
        assert placeholder in source, resource


def test_ingress_dns_hosts_expose_safe_direct_open_actions() -> None:
    backend = read('app/kubernetes/inventory/resources/ingresses.py')
    detail = read('app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html')

    assert 'def _host_access_rows(' in backend
    assert "scheme = 'https' if host in tls_hosts else 'http'" in backend
    assert "'url': f'{scheme}://{host}' if direct else None" in backend
    assert "'host_access_rows': _host_access_rows(hosts, context['tls_entries'])" in backend
    assert 'data-kaori-ingress-dns-access' in detail
    assert '>DNS Hosts</p>' in detail
    assert 'target="_blank"' in detail
    assert 'rel="noopener noreferrer"' in detail
    assert 'aria-label="Open {{ host.host }}"' in detail
    assert "metadata_label('Reference Only', 'globe-2')" in detail


def test_inventory_usability_polish_stays_on_kaori_semantic_tokens() -> None:
    files = [
        'app/templates/components/details/_detail_content.html',
        'app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html',
        'app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html',
    ]
    forbidden = ('#7C3AED', '#6D28D9', '#5B21B6', 'text-[', 'bg-[', 'border-[#', 'font-extrabold')
    for file in files:
        source = read(file)
        for token in forbidden:
            assert token not in source, (file, token)
