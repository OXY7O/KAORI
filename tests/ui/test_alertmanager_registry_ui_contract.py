from pathlib import Path


def test_alertmanager_registry_uses_automatic_htmx_filters() -> None:
    source = Path(
        'app/templates/integrations/alertmanager/partials/_inventory_card.html'
    ).read_text(encoding='utf-8')

    required_fragments = (
        'id="alertmanager-inventory-filter-form"',
        'hx-target="#alertmanager-inventory-content"',
        'hx-swap="innerHTML"',
        'hx-push-url="true"',
        'change from:select',
        "keyup changed delay:500ms from:input[name='q']",
        "search from:input[name='q']",
        'hx-indicator="#alertmanager-inventory-loading"',
        '<input type="hidden" name="page" value="1">',
        '<input type="hidden" name="per_page" value="{{ pagination.per_page }}">',
        "{% include 'integrations/alertmanager/partials/_inventory_content.html' %}",
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager registry HTMX contract is incomplete: {missing}'
    assert '>Apply<' not in source
    assert 'type="submit"' not in source


def test_alertmanager_registry_copy_uses_global_operational_positioning() -> None:
    source = Path(
        'app/templates/integrations/alertmanager/partials/_inventory_card.html'
    ).read_text(encoding='utf-8')

    assert 'Manage reusable alert connections and the operational scopes that can use them.' in source
    assert 'analytics domain may consume each source' not in source
    assert 'Compatibility' in source

