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


def test_kubernetes_inventory_modal_values_keep_identifiers_without_copy_controls() -> None:
    sources = {
        'overview': 'app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html',
        'nodes': 'app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html',
        'namespaces': 'app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html',
        'workloads': 'app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html',
        'pods': 'app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html',
        'services': 'app/templates/kubernetes/inventory/services/partials/_service_detail_content.html',
        'ingresses': 'app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html',
        'storage': 'app/templates/kubernetes/inventory/storage/partials/_storage_detail_content.html',
        'configuration': 'app/templates/kubernetes/inventory/configuration/partials/_configuration_detail_content.html',
    }
    for resource, path in sources.items():
        template = read(path)
        assert 'data-kaori-inventory-detail="v10"' in template, resource
        assert 'copyable=true' not in template, resource
        assert 'data-kaori-copy-button' not in template, resource
        assert 'data-kaori-copy-root' not in template, resource

    for path, expected in (
        (
            'app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html',
            "inventory_technical_row('UID', namespace.uid)",
        ),
        (
            'app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html',
            "inventory_technical_row('UID', workload.uid)",
        ),
        (
            'app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html',
            "inventory_technical_row('Kubernetes UID', pod.uid)",
        ),
        (
            'app/templates/kubernetes/inventory/services/partials/_service_detail_content.html',
            "inventory_technical_row('Kubernetes UID', service.uid)",
        ),
        (
            'app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html',
            "inventory_technical_row('Kubernetes UID', ingress.uid)",
        ),
        (
            'app/templates/kubernetes/inventory/storage/partials/_storage_detail_content.html',
            "inventory_technical_row('Kubernetes UID', item.uid)",
        ),
    ):
        assert expected in read(path)

    node = read(sources['nodes'])
    assert "inspector_technical_row('System UUID', node.system_uuid" in node
    assert "inspector_technical_row('Internal IP', node.internal_ip" in node
    assert "inspector_technical_row('External IP', node.external_ip" in node
    pod_projection = read('app/kubernetes/inventory/resources/pod_detail.py')
    assert "'label': 'Pod IP', 'value': pod.pod_ip or unknown" in pod_projection
    assert "'label': 'Host IP', 'value': details.get('host_ip') or unknown" in pod_projection
    assert "'copyable': True" not in pod_projection
    assert "{'label': 'Cluster IP', 'value': service.cluster_ip}" in read(sources['services'])


def test_shared_inventory_renderers_ignore_legacy_copy_flags() -> None:
    from jinja2 import Environment, FileSystemLoader

    source = read('app/templates/components/details/_detail_content.html')
    for macro in ('inventory_technical_row', 'inspector_technical_row', 'inventory_fact_grid'):
        body = source.split('{% macro ' + macro + '(', 1)[1].split('{%- endmacro %}', 1)[0]
        assert 'data-kaori-copy-' not in body, macro
        assert 'inventory_copy_button(' not in body, macro
        assert 'data-lucide="copy"' not in body, macro

    # Retain the signature for existing callers without re-enabling Inventory clipboard.
    assert (
        "macro inventory_technical_row(label, value='-', break_all=false, nowrap=false, class_name='', copyable=false)"
    ) in source

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    module = env.get_template('components/details/_detail_content.html').module
    uid = '7f1769e7-f7a7-42e1-82f0-2898557100e3'
    ip = '10.21.18.8'
    renderings = (
        str(module.inventory_technical_row('UID', uid)),
        str(module.inventory_technical_row('UID', uid, copyable=True)),
        str(module.inventory_technical_row('UID', uid, copyable=False)),
        str(module.inspector_technical_row('System UUID', uid, copyable=True)),
        str(module.inventory_fact_grid([{'label': 'Pod IP', 'value': ip, 'copyable': True}], columns=2)),
    )
    for rendered, value in zip(renderings, (uid, uid, uid, uid, ip), strict=True):
        assert value in rendered
        assert 'data-kaori-copy-' not in rendered
        assert 'data-lucide="copy"' not in rendered
        assert 'aria-label="Copy ' not in rendered
        assert '<button' not in rendered

    # The named helper is kept for compatibility; none of the Inventory fact
    # renderers above may invoke it. Global clipboard support is untouched.
    assert 'macro inventory_copy_button(label)' in source
    assert 'data-kaori-copy-button' in source


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
    assert 'table_label.metadata_label(badge, none, false, badge_size)' in shared
    assert 'Cluster name, version, connection.' in cluster
    assert 'Collection, source, freshness.' in cluster
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

    assert (
        'Unset controls remain neutral pending policy review; PSA defaults are not inferred, '
        'and ServiceAccount presence is separate evidence.'
    ) in detail
    assert 'Controls that are not explicitly set at namespace level remain neutral evidence' not in detail
    assert 'data-kaori-reported-quota' in detail
    assert 'Configured hard limits' in detail
    assert '>Resource</span>' in detail
    assert '>Hard Limit</span>' in detail
    assert 'divide-y divide-outline-subtle' in detail


def test_inventory_operational_guidance_copy_is_compact_and_evidence_qualified() -> None:
    expected = {
        'app/templates/kubernetes/inventory/namespaces/partials/_namespace_detail_content.html': (
            (
                'Unset controls remain neutral pending policy review; PSA defaults are not inferred, '
                'and ServiceAccount presence is separate evidence.'
            ),
        ),
        'app/templates/kubernetes/inventory/services/partials/_service_detail_content.html': (
            'Committed backend addresses.',
            'Selector-matched Pods in snapshot.',
            'Committed Service and backends; live traffic and public exposure unverified.',
        ),
        'app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html': (
            (
                'Resolved Secret confirms committed presence, not certificate content, '
                'expiry, key match or host coverage.'
            ),
            'Service references use committed inventory; resource backends remain declarations, not live endpoints.',
            'Committed Ingress evidence; exposure, DNS, traffic, reachability, and certificate validity unverified.',
        ),
        'app/templates/kubernetes/inventory/storage/partials/_storage_detail_content.html': (
            'Committed storage bindings; live usage, pressure, growth, durability, and I/O health unverified.',
        ),
        'app/templates/kubernetes/inventory/configuration/partials/_configuration_detail_content.html': (
            'No Pod references in snapshot; other consumers may exist.',
            'Committed key metadata and Pod references; no live API query or exposed values.',
        ),
        'app/kubernetes/inventory/resources/pod_semantics.py': (
            'Container restarts recorded in the snapshot; check runtime before treating them as active.',
        ),
        'app/kubernetes/inventory/resources/service_semantics.py': (
            'Backend registration committed; traffic and reachability remain unverified.',
        ),
        'app/kubernetes/inventory/resources/ingresses.py': (
            'No TLS Secret declared; neutral until governance policy review.',
        ),
        'app/kubernetes/inventory/resources/storage.py': (
            'No exceptional lifecycle state in the committed storage snapshot.',
        ),
        'app/kubernetes/inventory/resources/configuration.py': (
            (
                'No Pod references in this snapshot; other consumers or workload templates '
                'may still reference this object.'
            ),
        ),
    }
    for path, descriptions in expected.items():
        source = read(path)
        for description in descriptions:
            assert description in source, (path, description)
            assert len(description) <= 133, (path, description)

    service = read('app/kubernetes/inventory/resources/service_semantics.py')
    ingress = read('app/kubernetes/inventory/resources/ingresses.py')
    storage = read('app/kubernetes/inventory/resources/storage.py')
    configuration = read('app/kubernetes/inventory/resources/configuration.py')
    pod = read('app/kubernetes/inventory/resources/pod_semantics.py')
    assert "'Service Snapshot Ready for Review'" in service
    assert "'TLS Reference Not Configured'" in ingress
    assert "'Storage Snapshot Ready for Review'" in storage
    assert "'No Current Pod References'" in configuration
    assert "'Review Restart Activity'" in pod


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
