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

    assert 'data-kaori-inventory-section-layout="horizontal-band"' in shared
    assert 'lg:grid-cols-[14rem_minmax(0,1fr)]' in shared
    assert 'lg:border-r' in shared
    assert 'bg-surface-elevated/50' in shared
    assert "badge_size='detail'" in shared

    for resource, filename in DETAILS.items():
        detail = read(f'app/templates/kubernetes/inventory/{resource}/partials/{filename}')
        if resource == 'nodes':
            assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
            assert 'data-kaori-inventory-detail="v10"' in detail
            assert 'data-kaori-inventory-detail-layout="unified-resource-sheet"' in detail
            assert 'detail.inspector_section(' in detail
            continue
        assert 'data-kaori-detail-density="horizontal-bands"' in detail, resource
        assert 'data-kaori-inventory-detail="v6"' in detail, resource
        assert 'data-kaori-inventory-detail-layout="horizontal-section-stack"' in detail, resource
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
        "special_label(total_count ~ ' ' ~ ('Resource' if total_count == 1 else 'Resources'), 'maintenance', 'git-branch', 'detail')"
        in related
    )
    assert "special_label(taint_count_label, 'maintenance', 'tags', 'detail')" in node


def test_factual_field_typography_remains_one_body_scale() -> None:
    shared = read('app/templates/components/details/_detail_content.html')

    assert 'text-sm font-normal leading-5 text-content-secondary' in shared
    assert 'text-left text-sm font-medium leading-5 text-content-primary' in shared
    assert "technical_classes = 'font-medium xl:whitespace-nowrap' if nowrap else 'font-medium'" in shared
