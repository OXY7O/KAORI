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
    assert 'data-kaori-inventory-section-layout="resource-sheet-band"' in shared
    assert 'bg-surface-elevated/35 px-6 py-5' in shared
    assert 'sm:px-7' in shared
    assert 'xl:px-8 xl:py-6' in shared

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


def test_inventory_copy_controls_are_shared_while_node_identifiers_are_read_only() -> None:
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
    assert "inventory_technical_row('UID', namespace.uid)" in namespace
    assert "inventory_technical_row('UID', namespace.uid, copyable=true)" not in namespace
    assert "inventory_technical_row('UID', workload.uid, copyable=true)" in workload
    assert "inventory_technical_row('Kubernetes UID', pod.uid, copyable=true)" in pod
    assert "inventory_technical_row('Kubernetes UID', service.uid, copyable=true)" in service
    assert "inventory_technical_row('Kubernetes UID', ingress.uid, copyable=true)" in ingress
    assert "inventory_technical_row('Kubernetes UID', item.uid, copyable=true)" in storage
    assert "macro inspector_technical_row(label, value='-', nowrap=false, class_name='', copyable=false)" in shared
    assert "inspector_technical_row('System UUID', node.system_uuid" in node
    assert 'copyable=true' not in node
    assert "inspector_technical_row('Internal IP', node.internal_ip or 'Not Reported', nowrap=true)" in node
    assert "inspector_technical_row('External IP', node.external_ip or 'Not Reported', nowrap=true)" in node
    assert "'label': 'Pod IP', 'value': pod.pod_ip or unknown, 'copyable': True" in pod_detail
    assert "'label': 'Host IP', 'value': details.get('host_ip') or unknown, 'copyable': True" in pod_detail
    assert "{'label': 'Cluster IP', 'value': service.cluster_ip, 'copyable': true}" in service


def test_cluster_and_node_detail_section_descriptions_are_concise() -> None:
    cluster = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    for description in (
        'Cluster name, version, connection.',
        'Collection, source, freshness.',
        'Committed objects by resource type.',
        'Collection and operational signals.',
    ):
        assert f"description='{description}'" in cluster
    for description in (
        'Node identity and snapshot.',
        'IPs, hostnames, network.',
        'CPU, memory, disk capacity.',
        'OS, kernel, runtime versions.',
        'Readiness, pressure, taints.',
    ):
        assert description in node

    assert 'Committed object coverage across the Kubernetes inventory domains' not in cluster
    assert 'Canonical node identity, cluster placement, lifecycle age' not in node
    assert 'Node addressing, hostname, and network-scope evidence' not in node
    assert 'Reported compute, memory, and ephemeral storage capacity;' not in node
    assert 'Host OS, kernel, container runtime, and Kubernetes component versions' not in node
    assert 'Placement eligibility, readiness, pressure conditions' not in node




def test_cluster_breakdown_uses_existing_metadata_badge_without_health_claim() -> None:
    cluster = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')

    assert (
        "detail.inventory_section('Inventory Breakdown', 'boxes', "
        "cluster.populated_asset_types ~ '/8 Types', "
        "description='Committed objects by resource type.')"
    ) in cluster
    assert "macro inventory_section(title, icon, badge=None, badge_type='metadata'" in shared
    assert "table_label.metadata_label(badge, none, false, badge_size)" in shared
    assert "Cluster name, version, connection." in cluster
    assert "Collection, source, freshness." in cluster
    assert 'data-kaori-inventory-section-description' in shared
    assert 'break-words text-xs leading-5' in shared

def test_namespace_detail_context_is_compact_and_uid_has_no_clipboard_control() -> None:
    from jinja2 import Environment, FileSystemLoader

    detail = read('app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html')
    descriptions = (
        'Identity, lifecycle, snapshot.',
        'Pod security and access.',
        'Workloads, network, config.',
        'Quota and limit controls.',
    )
    for description in descriptions:
        assert f"description='{description}'" in detail

    assert "detail.inventory_technical_row('UID', namespace.uid)" in detail
    assert "detail.inventory_technical_row('UID', namespace.uid, copyable=true)" not in detail

    environment = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    uid_row = environment.get_template('components/details/_detail_content.html').module.inventory_technical_row
    rendered = str(uid_row('UID', '7f1769e7-f7a7-42e1-82f0-2898557100e3'))
    assert '7f1769e7-f7a7-42e1-82f0-2898557100e3' in rendered
    for element in ('data-kaori-copy-root', 'data-kaori-copy-source', 'data-kaori-copy-button', 'data-lucide="copy"'):
        assert element not in rendered


def test_all_kubernetes_inventory_detail_rails_use_bounded_copy() -> None:
    expected = {
        'nodes': (
            'Node identity and snapshot.',
            'IPs, hostnames, network.',
            'CPU, memory, disk capacity.',
            'OS, kernel, runtime versions.',
            'Readiness, pressure, taints.',
        ),
        'namespaces': (
            'Identity, lifecycle, snapshot.',
            'Pod security and access.',
            'Workloads, network, config.',
            'Quota and limit controls.',
        ),
        'workloads': (
            'Ownership, type, snapshot.',
            'Replicas and rollout state.',
            'Containers and Pod settings.',
            'Rollout, exposure, placement.',
            'Pods owned by this workload.',
        ),
        'pods': (
            'Pod identity and snapshot.',
            'Phase, readiness, restarts.',
            'Node, IPs, scheduling.',
            'QoS, containers, security.',
            'ConfigMap/Secret names only.',
            'Referenced PersistentVolumeClaims.',
        ),
        'services': (
            'Service type and snapshot.',
            'IPs, ports, external access.',
            'Endpoints and Pod selectors.',
            'Traffic and IP policies.',
        ),
        'ingresses': (
            'Ingress identity and class.',
            'Hosts, addresses, publication.',
            'Declared TLS Secret bindings.',
            'Host and backend routes.',
            'Committed Service references.',
            'Committed TLS Secret links.',
        ),
        'storage': (
            'Storage identity and scope.',
            'Capacity, access, modes.',
            'Binding and lifecycle state.',
            'Provisioner and settings.',
            'Committed claim references.',
            'Pods mounting related claims.',
        ),
        'configuration': (
            'Object identity and snapshot.',
            'Sensitive values not stored.',
            'Current Pod references.',
            'Pods referencing this object.',
        ),
    }
    for family, captions in expected.items():
        path = (
            f'app/templates/kubernetes/inventory/{family}/partials/'
            f'_{family[:-1] if family.endswith("s") and family not in ("ingresses", "services", "namespaces") else family}_detail_content.html'
        )
        # Explicit path mapping below retains the repository's canonical resource names.
        path = {
            'nodes': 'app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html',
            'namespaces': 'app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html',
            'workloads': 'app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html',
            'pods': 'app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html',
            'services': 'app/templates/kubernetes/inventory/services/partials/_service_detail_content.html',
            'ingresses': 'app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html',
            'storage': 'app/templates/kubernetes/inventory/storage/partials/_storage_detail_content.html',
            'configuration': 'app/templates/kubernetes/inventory/configuration/partials/_configuration_detail_content.html',
        }[family]
        source = read(path)
        assert 'data-kaori-inventory-detail="v10"' in source, family
        for caption in captions:
            assert len(caption) <= 36, (family, caption)
            assert caption in source, (family, caption)

    metadata = read('app/templates/components/technical_metadata_collection.html')
    assert "'Committed metadata entries.'" in metadata
    assert "'Key names only; no values.'" in metadata
    assert 'data-kaori-inventory-section-description' in metadata


def test_node_missing_section_badges_use_committed_fields_not_health_inference() -> None:
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')
    shared = read('app/templates/components/details/_detail_content.html')
    for call in (
        "detail.inspector_section('Identity & Snapshot', 'badge-info', 'Node identity and snapshot.', '', node.age)",
        "detail.inspector_section('Node Capacity', 'gauge', 'CPU, memory, disk capacity.', '', node.cpu_display)",
        "detail.inspector_section('Runtime & Platform', 'terminal-square', 'OS, kernel, runtime versions.', '', node.kubelet_version)",
    ):
        assert call in node
    assert "macro inspector_section(title, icon, description=None, class_name='', badge=None," in shared
    assert "badge_type='metadata'" in shared
    assert "table_label.special_label(badge, 'maintenance', 'tags', 'detail')" in shared
    assert "node.network_availability, 'status', network_tone" in node
    assert "condition_posture, 'status', condition_tone" in node


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
