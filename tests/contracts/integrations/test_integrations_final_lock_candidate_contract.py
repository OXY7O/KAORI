from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_shared_record_detail_and_action_contract_is_canonical() -> None:
    actions = read('app/templates/integrations/components/_record_actions.html')
    runtime_modal = read('app/templates/integrations/components/_runtime_observation_modal.html')

    assert '{% import "components/table.html" as table_ui %}' in actions
    assert '{{ table_ui.action_classes() }}' in actions
    assert 'data-lucide="chevron-right"' in actions
    assert 'panel-top-open' not in actions
    assert 'record_detail_modal.render(' in runtime_modal
    assert "size='standard'" in runtime_modal
    assert '<dialog' not in runtime_modal
    assert 'data-kaori-runtime-observation-diagnostic-review' in runtime_modal
    assert 'row.standalone_message' in runtime_modal


def test_provider_configuration_uses_shared_side_decision() -> None:
    shared = read('app/templates/integrations/components/_configuration_decision.html')
    assert 'data-kaori-configuration-decision-side' in shared
    assert 'Controlled Flow' in shared
    assert 'flex h-full min-h-full flex-col self-stretch' in shared
    assert 'xl:sticky xl:top-4' not in shared
    for provider in ('prometheus', 'alertmanager'):
        source = read(f'app/templates/{provider}/partials/_detail_configuration.html')
        assert 'configuration_decision.side_panel(' in source
        assert 'grid-cols-[minmax(0,1fr)_25rem]' in source
        assert 'items-stretch' in source
        assert 'embedded=true' in source


def test_provider_tabs_share_one_controller() -> None:
    controller = read('app/static/js/integration_workspace_tabs.js')
    layout = read('app/templates/layouts/app.html')
    assert 'window.integrationWorkspaceTabs' in controller
    assert 'integration_workspace_tabs.js' in layout
    for provider in ('prometheus', 'alertmanager'):
        assert 'integrationWorkspaceTabs(' in read(f'app/templates/{provider}/instance_detail.html')


def test_runtime_overview_uses_modal_and_registry_tables_avoid_forced_scroll() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')
    modal = read('app/templates/integrations/partials/_runtime_overview_modal.html')
    assert 'record_actions.view_more(' in runtime
    assert "role='runtime-overview'" in runtime
    assert 'expandable_row' not in runtime
    assert 'table-fixed' in runtime
    assert '<col class="w-[10%]">' in runtime
    assert 'table_ui.cell_classes(true) }} whitespace-nowrap' in runtime
    assert "table_ui.table_classes('min-w-[78rem]')" not in runtime
    assert 'record_detail_modal.render(' in modal

    pairs = [
        ('app/templates/integrations/kubernetes/partials/_registry.html', 'min-w-[1040px]'),
        ('app/templates/integrations/prometheus/partials/_inventory_content.html', 'min-w-[1080px]'),
        ('app/templates/integrations/alertmanager/partials/_inventory_content.html', 'min-w-[1040px]'),
    ]
    registry_component = read('app/templates/integrations/components/_provider_registry.html')
    assert 'connection_registry_head()' in registry_component
    for path, legacy_width in pairs:
        source = read(path)
        assert 'table-fixed' not in source
        assert legacy_width not in source
        assert 'provider_registry.connection_registry_table_classes()' in source
        assert 'provider_registry.connection_registry_head()' in source
