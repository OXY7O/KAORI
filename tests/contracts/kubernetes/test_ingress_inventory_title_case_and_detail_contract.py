from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_ingress_inventory_uses_canonical_resource_page_pattern() -> None:
    hero = read('app/templates/inventory/ingresses/partials/_hero.html')
    summary = read('app/templates/inventory/ingresses/partials/_summary_cards.html')
    table = read('app/templates/inventory/ingresses/partials/_table_content.html')

    assert 'page_hero.context_card(' in hero
    assert 'Ingress Publication Posture' in summary
    assert 'posture_grid.render(metrics, columns=3)' in summary
    for column in ('Ingress', 'Scope', 'Publication', 'TLS References', 'Routing', 'Details'):
        assert column in table
    assert 'table_ui.namespaced_scope_identity(' in table
    assert 'resource_detail_modal.detail_button(' in table


def test_ingress_detail_uses_adaptive_stacks_and_factual_tls_evidence() -> None:
    detail = read('app/templates/inventory/ingresses/partials/_ingress_detail_content.html')
    service = read('app/inventory/resources/ingresses.py')

    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert 'detail.expanded_workspace_shell_classes()' in detail
    assert 'TLS Secret References' in detail
    assert 'does not validate certificate existence, validity, expiry, or hostname coverage' in detail
    assert 'Open Declared Host' in detail
    assert 'Reference State' in detail
    assert "'Resolve Backend References'" in service
    assert "'TLS Reference Not Configured'" in service
    assert 'No TLS Reference' in detail
    assert 'TLS review' not in detail
    assert 'TLS covered' not in detail


def test_ingress_backend_services_resolve_against_committed_service_inventory() -> None:
    service = read('app/inventory/resources/ingresses.py')
    detail = read('app/templates/inventory/ingresses/partials/_ingress_detail_content.html')

    assert 'filter_current_generation(ServiceInventory.query, ServiceInventory)' in service
    assert "'reference_state': state" in service
    assert "'Resolved'" in service
    assert "'Missing'" in service
    assert "related_collection.render('Backend Services'" in detail
    assert "url_for('inventory.services'" in detail


def test_ingress_page_size_refreshes_owning_scope() -> None:
    table = read('app/templates/inventory/ingresses/partials/_table_content.html')
    card = read('app/templates/inventory/ingresses/partials/_table_card.html')

    assert 'hx-target="#ingresses-inventory-scope"' in table
    assert 'name="partial_mode" value="inventory_scope"' in table
    assert '>Rows</label>' in table
    assert "endpoint='inventory.ingresses'" in table
    assert "hx-trigger=\"change, keyup changed delay:500ms from:find input[name='search']\"" in card
