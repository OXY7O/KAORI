from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_ingress_inventory_uses_canonical_resource_page_pattern() -> None:
    routes = read('app/kubernetes/inventory/routes.py')
    workspace = read('app/templates/kubernetes/inventory/ingresses/partials/_page_workspace.html')
    hero = read('app/templates/kubernetes/inventory/ingresses/partials/_hero.html')
    summary = read('app/templates/kubernetes/inventory/ingresses/partials/_summary_cards.html')
    card = read('app/templates/kubernetes/inventory/ingresses/partials/_table_card.html')
    table = read('app/templates/kubernetes/inventory/ingresses/partials/_table_content.html')

    assert (
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes
    )
    assert 'id="ingresses-page-workspace"' in workspace
    assert 'kubernetes/inventory/components/_data_freshness.html' in workspace
    assert 'page_hero.context_card(' in hero
    assert 'Ingress Publication Posture' in summary
    assert 'inventory.total_ingresses == 0' in summary
    assert 'posture_grid.render(metrics, columns=3)' in summary
    assert 'hx-target="#ingresses-page-workspace"' in card
    assert 'name="partial_mode" value="page_workspace"' in card
    assert 'aria-label="Ingress inventory filters"' in card
    for column in ('Ingress', 'Scope', 'Publication', 'TLS References', 'Routing', 'Details'):
        assert column in table
    assert '<caption class="sr-only">' in table
    assert table.count('scope="col"') == 6
    assert 'table_ui.namespaced_scope_identity(' in table
    assert 'resource_detail_modal.detail_button(' in table
    assert ' · Age ' not in table


def test_ingress_detail_uses_adaptive_stacks_and_factual_reference_evidence() -> None:
    detail = read('app/templates/kubernetes/inventory/ingresses/partials/_ingress_detail_content.html')
    service = read('app/kubernetes/inventory/resources/ingresses.py')
    semantics = read('app/kubernetes/inventory/resources/ingress_semantics.py')

    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert 'detail.expanded_workspace_shell_classes()' in detail
    assert 'TLS Secret References' in detail
    assert 'does not validate certificate contents, expiry, key matching, or hostname coverage' in detail
    assert 'Reference State' in detail
    assert '<caption class="sr-only">Declared backend routes for Ingress' in detail
    assert detail.count('scope="col"') >= 6
    assert "related_collection.render('Backend Services'" in detail
    assert "related_collection.render('TLS Secret References'" in detail
    assert "url_for('inventory.services'" in detail
    assert "url_for('inventory.configuration'" in detail
    assert "'Resolve Backend Service References'" in service
    assert "'Resolve TLS Secret References'" in service
    assert "'TLS Reference Not Configured'" in service
    assert "return 'Not Reported', 'unknown'" in semantics
    assert 'Open Declared Host' not in detail


def test_ingress_reference_resolution_honors_committed_collection_evidence() -> None:
    service = read('app/kubernetes/inventory/resources/ingresses.py')
    semantics = read('app/kubernetes/inventory/resources/ingress_semantics.py')

    assert 'filter_current_generation(ServiceInventory.query, ServiceInventory)' in service
    assert 'filter_current_generation(ConfigurationInventory.query, ConfigurationInventory)' in service
    assert "evidence.get('inventory.services')" in service
    assert "evidence.get('inventory.secrets')" in service
    assert 'service_collection_state != COLLECTED' in semantics
    assert 'secret_collection_state != COLLECTED' in semantics
    assert "return 'Missing', 'critical'" in semantics
    assert "return 'Resource Backend', 'info'" in semantics


def test_ingress_page_size_and_pagination_use_canonical_boundaries() -> None:
    table = read('app/templates/kubernetes/inventory/ingresses/partials/_table_content.html')
    card = read('app/templates/kubernetes/inventory/ingresses/partials/_table_card.html')

    assert 'hx-target="#ingresses-table-content"' in table
    assert 'name="partial_mode" value="table_content"' in table
    assert '>Rows</label>' in table
    assert "endpoint='inventory.ingresses'" in table
    assert 'hx-target="#ingresses-page-workspace"' in card
    assert 'hx-trigger="change, keyup changed delay:500ms from:find input[name=\'search\']"' in card


def test_ingress_legacy_scope_wrapper_is_removed() -> None:
    assert not (ROOT / 'app/templates/kubernetes/inventory/ingresses/partials/_inventory_scope.html').exists()
