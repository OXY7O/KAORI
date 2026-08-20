from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_service_inventory_uses_canonical_resource_page_pattern() -> None:
    hero = read('app/templates/kubernetes/inventory/services/partials/_hero.html')
    summary = read('app/templates/kubernetes/inventory/services/partials/_summary_cards.html')
    table = read('app/templates/kubernetes/inventory/services/partials/_table_content.html')

    assert 'page_hero.context_card(' in hero
    assert 'Service Network Posture' in summary
    assert 'posture_grid.render(metrics, columns=3)' in summary
    for column in ('Service', 'Scope', 'Access Model', 'Port Mapping', 'Backend Registration', 'Details'):
        assert column in table
    assert 'table_ui.namespaced_scope_identity(' in table
    assert 'status_indicator_label(service.backend.label' in table
    assert 'resource_detail_modal.detail_button(' in table


def test_service_detail_uses_adaptive_stacks_and_factual_network_configuration() -> None:
    detail = read('app/templates/kubernetes/inventory/services/partials/_service_detail_content.html')
    semantics = read('app/kubernetes/inventory/resources/service_semantics.py')

    assert 'data-kaori-detail-density="horizontal-bands"' in detail
    assert 'detail.expanded_workspace_shell_classes()' in detail
    assert 'Technical Metadata Collection' not in detail
    assert 'metadata_collection.render(' in detail
    assert 'related_collection.inventory_render(' in detail
    assert 'Traffic policies and publication configuration remain factual evidence' in detail
    assert "status_row('IP Family Policy'" not in detail
    assert "'No Registered Backends'" in semantics
    assert "'External Destination'" in semantics
    assert "'Manually Managed'" in semantics


def test_service_collection_prefers_endpoint_slice_with_endpoints_fallback() -> None:
    collector = read('app/kubernetes/inventory/collectors/services.py')
    sync = read('app/kubernetes/inventory/synchronization.py')

    assert 'list_endpoint_slice_for_all_namespaces' in collector
    assert "'EndpointSlice'" in collector
    assert 'list_endpoints_for_all_namespaces' in collector
    assert "'Endpoints'" in collector
    assert 'DiscoveryV1Api(core_api.api_client)' in sync


def test_service_filters_and_page_size_refresh_the_complete_workspace() -> None:
    table = read('app/templates/kubernetes/inventory/services/partials/_table_content.html')
    card = read('app/templates/kubernetes/inventory/services/partials/_table_card.html')

    assert 'hx-target="#services-table-content"' in table
    assert 'name="partial_mode" value="table_content"' in table
    assert '>Rows</label>' in table
    assert "endpoint='inventory.services'" in table
    assert 'hx-target="#services-page-workspace"' in card
    assert 'name="partial_mode" value="page_workspace"' in card
    assert 'hx-trigger="change, keyup changed delay:500ms from:find input[name=\'search\']"' in card
