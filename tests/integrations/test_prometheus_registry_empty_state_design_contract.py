from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_registry_table_header_is_always_rendered():
    source = (
        ROOT
        / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')

    table_position = source.index('<table')
    header_position = source.index('<thead')
    loop_position = source.index('{% for row in rows %}')

    assert table_position < header_position < loop_position
    assert '{% if rows %}' not in source


def test_prometheus_empty_state_is_rendered_inside_table_body():
    source = (
        ROOT
        / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')

    assert '{% else %}' in source
    assert '<td colspan="8" class="p-0">' in source
    assert "empty_state_title = 'No Prometheus Connections Found'" in source
    assert (
        "empty_state_description = 'Register a Prometheus connection "
        "or adjust the active filters.'"
    ) in source
    assert "empty_state_action_label = 'Register Connection'" in source


def test_prometheus_registry_footer_remains_visible_for_empty_results():
    source = (
        ROOT
        / 'app/templates/integrations/prometheus/partials/_inventory_content.html'
    ).read_text(encoding='utf-8')

    empty_state_position = source.index(
        "empty_state_title = 'No Prometheus Connections Found'"
    )
    footer_position = source.index(
        'border-t border-outline-subtle bg-surface-hover'
    )

    assert empty_state_position < footer_position
    assert 'pagination.total_items' in source
