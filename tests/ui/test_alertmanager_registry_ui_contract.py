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


def test_alertmanager_registry_content_uses_kaori_table_contract() -> None:
    source = Path(
        'app/templates/integrations/alertmanager/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')

    required_fragments = (
        'components/table_label.html',
        'table_label.status_label',
        'table_label.metadata_label',
        'text-right">Action',
        'aria-label="Rows per page"',
        '<option value="{{ value }}"',
        'pagination.allowed_per_page',
        'Page {{ pagination.page }} / {{ pagination.total_pages }}',
        'cursor-not-allowed',
        'components/states/_empty_state.html',
        'hx-target="#alertmanager-inventory-content"',
        'hx-indicator="#alertmanager-inventory-loading"',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager registry table contract is incomplete: {missing}'
