from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates/kubernetes/inventory'


def read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding='utf-8')


def test_kubernetes_inventory_tables_keep_bounded_columns() -> None:
    for family in (
        'storage', 'ingresses', 'configuration', 'pods',
        'services', 'nodes', 'namespaces', 'workloads',
    ):
        content = read(f'{family}/partials/_table_content.html')
        assert '!table-fixed' in content, family
        assert 'overflow-x-auto' in content, family
        assert 'table_ui.title_cell(' in content or 'table_ui.namespace_identity(' in content, family


def test_storage_and_ingress_keep_full_identity_available_in_title() -> None:
    storage = read('storage/partials/_table_content.html')
    ingress = read('ingresses/partials/_table_content.html')
    assert 'title="{{ item.capacity_secondary }}"' in storage
    assert 'title="{{ item.binding_secondary }}"' in storage
    assert 'title="{{ ingress.host }}"' in ingress
    assert 'title="{{ ingress.address }}"' in ingress
    assert 'status_indicator_label(ingress.publication_label' in ingress


def test_ingress_publication_uses_proportional_space_and_two_level_evidence() -> None:
    ingress = read('ingresses/partials/_table_content.html')
    for heading, width in (
        ('Ingress', '19%'),
        ('Scope', '16%'),
        ('Publication', '30%'),
        ('TLS References', '13%'),
        ('Routing', '10%'),
        ('Details', '12%'),
    ):
        assert f'w-[{width}]">{heading}' in ingress

    assert 'class="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1"' in ingress
    assert 'title="{{ ingress.host }}"' in ingress
    assert 'title="{{ ingress.host_supporting }}"' in ingress
    assert 'title="{{ ingress.address }}"' in ingress
    assert 'status_indicator_label(ingress.publication_label, ingress.publication_tone)' in ingress
    assert '{{ ingress.address or "Not Reported" }}' in ingress
    assert "table_ui.table_classes('min-w-[72rem] !table-fixed')" in ingress
    assert 'resource_detail_modal.detail_button(ingress.id' in ingress


def test_pod_references_use_shared_full_width_evidence_bands() -> None:
    detail = read('pods/partials/_pod_detail_content.html')
    assert 'aria-label="Pod Configuration and Storage References"' in detail
    assert 'configuration references exist.\', embedded=true)' in detail
    assert 'storage references exist.\', embedded=true)' in detail
    assert 'grid gap-4 border-t border-outline-subtle p-4 lg:grid-cols-2' not in detail
