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


def test_inventory_v6_uses_one_horizontal_band_contract() -> None:
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-inventory-section-layout="resource-sheet-band"' in shared
    assert 'xl:grid-cols-[14.5rem_minmax(0,1fr)]' in shared
    assert 'xl:border-r' in shared
    assert 'bg-surface-elevated/35' in shared
    assert "badge_size='detail'" in shared
    assert 'data-kaori-inventory-section-description' in shared
    assert 'absolute inset-y-0 left-0 w-0.5 bg-kaori-primary/70' in shared
    assert 'mt-3 hidden xl:flex' in shared

    for resource, filename in DETAILS.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        if resource == 'nodes':
            assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
            assert 'data-kaori-inventory-detail="v10"' in detail
            assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail
            assert 'detail.inspector_section(' in detail
            continue
        assert 'data-kaori-detail-density="unified-resource-sheet"' in detail, resource
        assert 'data-kaori-inventory-detail="v10"' in detail, resource
        assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail, resource
        assert 'detail.inventory_section(' in detail, resource


def test_primary_inventory_sections_do_not_use_peer_card_columns() -> None:
    forbidden = (
        'xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]',
        'xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]',
        'xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]',
        'xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]',
    )
    for resource, filename in DETAILS.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        for token in forbidden:
            assert token not in detail, (resource, token)


def test_inventory_tags_use_canonical_violet_label_treatment() -> None:
    metadata = read('app/templates/components/technical_metadata_collection.html')
    related = read('app/templates/components/related_resource_collection.html')
    node = read('app/templates/kubernetes/inventory/nodes/partials/_node_detail_content.html')

    assert "special_label(entry_count_label, 'maintenance', 'tags', 'detail')" in metadata
    assert (
        "special_label(total_count ~ ' ' ~ ('Resource' if total_count == 1 else 'Resources'), "
        "'maintenance', 'git-branch', 'detail')"
        in related
    )
    assert "special_label(taint_count_label, 'maintenance', 'tags', 'detail')" in node


def test_factual_field_typography_remains_one_body_scale() -> None:
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert "technical_classes = 'font-medium xl:whitespace-nowrap' if nowrap else 'font-medium'" in shared


def test_unified_inventory_sections_explain_their_evidence_scope() -> None:
    descriptions = {
        'overview': 'Registration, environment, Kubernetes version, and connectivity context for this cluster.',
        'namespaces': 'Canonical namespace identity, cluster ownership, lifecycle, and collection context.',
        'workloads': 'Workload identity, namespace ownership, controller type, age, and snapshot collection context.',
        'pods': 'Pod identity, namespace ownership, controller resolution, age, and collection timestamps.',
        'services': 'Service identity, namespace ownership, type, lifecycle age, and collection context.',
        'ingresses': 'Ingress identity, namespace ownership, class, lifecycle age, and collection context.',
        'storage': 'Storage resource identity, type, scope, lifecycle age, and committed collection context.',
        'configuration': 'Configuration object identity, namespace ownership, type, age, and collection context.',
    }

    overview = read('app/templates/kubernetes/inventory/overview/partials/_cluster_detail_content.html')
    assert descriptions['overview'] in overview
    for resource, filename in DETAILS.items():
        if resource == 'nodes':
            node = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
            assert (
                'Canonical node identity, cluster placement, lifecycle age, and committed collection context.' in node
            )
            continue
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        assert descriptions[resource] in detail, resource
