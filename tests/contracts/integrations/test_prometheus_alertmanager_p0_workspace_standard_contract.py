from pathlib import Path

ROOT = Path('.')


def read(path):
    return (ROOT / path).read_text()


def test_provider_overview_tabs_use_v2_framed_geometry():
    content = read('app/templates/components/integration_workspace_tabs.html')
    assert 'data-kaori-tab-variant="framed-workspace-v2"' in content
    assert '@keydown.arrow-right.prevent' in content
    assert 'x-on:popstate.window="syncTab()"' in content


def test_prometheus_registry_uses_one_line_filters_and_kaori_table():
    card = read('app/templates/integrations/prometheus/partials/_instance_inventory.html')
    table = read('app/templates/integrations/prometheus/partials/_inventory_content.html')
    assert 'data-kaori-one-line-filters' in card
    assert 'min-w-[820px]' in card
    assert 'table_ui.table_classes' in table
    assert 'table_ui.head_classes' in table
    assert "display='indicator'" in table
    assert "item_label='Integration'" in table


def test_alertmanager_registry_uses_one_line_filters_and_kaori_table():
    card = read('app/templates/integrations/alertmanager/partials/_inventory_card.html')
    table = read('app/templates/integrations/alertmanager/partials/_inventory_content.html')
    assert 'data-kaori-one-line-filters' in card
    assert 'min-w-[960px]' in card
    assert 'table_ui.table_classes' in table
    assert "display='indicator'" in table
    assert "item_label='Integration'" in table


def test_provider_detail_pages_use_tab_style_v2():
    for provider in ('prometheus', 'alertmanager'):
        content = read(f'app/templates/{provider}/instance_detail.html')
        assert 'components/framed_workspace_tabs.html' in content
        assert 'framed_workspace_tabs.render' in content
        assert "'Bindings & Consumers'" in content
        assert 'moveTab(currentTab, direction, prefix)' in content
        assert 'x-on:popstate.window="syncTabFromLocation()"' in content
