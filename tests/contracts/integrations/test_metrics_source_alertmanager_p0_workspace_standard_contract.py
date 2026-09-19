import json
from pathlib import Path

ROOT = Path('.')


def read(path):
    return (ROOT / path).read_text()


def test_provider_overview_tabs_use_v2_framed_geometry():
    content = read('app/templates/components/integration_workspace_tabs.html')
    assert 'data-kaori-tab-variant="framed-workspace-v2"' in content
    assert '@keydown.arrow-right.prevent' in content
    assert 'x-on:popstate.window="syncTab()"' in content


def test_metrics_source_registry_uses_one_line_filters_and_kaori_table():
    card = read('app/templates/integrations/observability/metrics_source/partials/_instance_inventory.html')
    table = read('app/templates/integrations/observability/metrics_source/partials/_inventory_content.html')
    assert 'data-kaori-one-line-filters' in card
    assert 'min-w-[820px]' not in card
    assert 'table-fixed' not in table
    assert "table_ui.table_classes('min-w-[1080px]')" not in table
    assert 'provider_registry.connection_registry_table_classes()' in table
    assert 'provider_registry.connection_registry_table_classes()' in table
    registry_component = read('app/templates/integrations/components/_provider_registry.html')
    assert 'table_ui.head_classes' in registry_component
    assert 'provider_registry.connection_registry_head()' in table
    assert 'display="indicator"' in table
    assert "item_label='Connections'" in table


def test_alertmanager_registry_uses_one_line_filters_and_kaori_table():
    card = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_card.html'
    )
    table = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html'
    )
    assert 'data-kaori-one-line-filters' in card
    assert 'min-w-[960px]' not in card
    assert 'table-fixed' not in table
    assert "table_ui.table_classes('min-w-[1040px]')" not in table
    assert 'provider_registry.connection_registry_table_classes()' in table
    assert 'provider_registry.connection_registry_table_classes()' in table
    assert 'display="indicator"' in table
    assert "item_label='Connections'" in table


def test_provider_detail_pages_use_shared_tab_style_v2_controller():
    controller = read('app/static/js/integration_workspace_tabs.js')
    assert 'window.integrationWorkspaceTabs' in controller
    assert 'moveTab(currentTab, direction' in controller
    for template_root in (
        'app/templates/integrations/observability/metrics_source',
        'app/templates/integrations/observability/alert_source/providers/alertmanager',
    ):
        content = read(f'{template_root}/instance_detail.html')
        assert 'components/framed_workspace_tabs.html' in content
        assert 'framed_workspace_tabs.render' in content
        assert "'Bindings & Consumers'" in content
        assert 'integrationWorkspaceTabs(' in content
        assert 'x-on:popstate.window="syncTab()"' in content


def test_observability_delete_modals_delegate_to_shared_destructive_runtime():
    shared_runtime = read('app/static/js/destructive_confirmation_modal.js')
    baseline = json.loads(read('docs/architecture/ui-inline-debt-baseline.json'))['files']
    providers = (
        (
            'metrics-source',
            'app/templates/integrations/observability/metrics_source',
            'metrics-source-delete-modal',
            'data-metrics-source-delete-button',
        ),
        (
            'alertmanager',
            'app/templates/integrations/observability/alert_source/providers/alertmanager',
            'alertmanager-delete-modal',
            'data-alertmanager-delete-button',
        ),
    )

    for provider, template_root, modal_id, legacy_trigger in providers:
        modal_path = f'{template_root}/partials/_delete_confirmation_modal.html'
        modal = read(modal_path)
        detail = read(f'{template_root}/instance_detail.html')
        scope = read(f'{template_root}/partials/_detail_scope.html')
        bindings = read(f'{template_root}/partials/_binding_registry.html')

        assert 'data-destructive-confirmation-modal' in modal
        assert 'data-destructive-modal-close' in modal
        assert 'data-destructive-dynamic-form' in modal
        assert 'data-destructive-modal-title' in modal
        assert 'data-destructive-target-name' in modal
        assert 'data-destructive-detail' in modal
        assert 'data-destructive-action-label' in modal
        assert '<script>' not in modal
        assert 'js/destructive_confirmation_modal.js' in detail

        for trigger_source in (scope, bindings):
            assert 'data-destructive-modal-open' in trigger_source
            assert f'data-destructive-modal-id="{modal_id}"' in trigger_source
            assert 'data-delete-url=' in trigger_source
            assert 'data-delete-title=' in trigger_source
            assert 'data-delete-name=' in trigger_source
            assert 'data-delete-detail=' in trigger_source
            assert 'data-delete-action-label=' in trigger_source
            assert legacy_trigger not in trigger_source

        assert modal_path not in baseline, provider

    assert 'button.dataset.deleteUrl' in shared_runtime
    assert "form.setAttribute('action', deleteUrl)" in shared_runtime
    assert "form.setAttribute('hx-post', deleteUrl)" in shared_runtime
    assert 'window.htmx.process(form)' in shared_runtime
    assert 'button.dataset.deleteTitle' in shared_runtime
    assert 'button.dataset.deleteName' in shared_runtime
    assert 'button.dataset.deleteDetail' in shared_runtime
    assert 'button.dataset.deleteActionLabel' in shared_runtime
    assert "'htmx:afterRequest'" in shared_runtime
