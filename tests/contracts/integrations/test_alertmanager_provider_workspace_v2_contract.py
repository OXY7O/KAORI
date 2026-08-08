from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_alertmanager_detail_uses_provider_v2_tabs_without_malformed_alpine_markup():
    content = read('app/templates/alertmanager/instance_detail.html')
    assert 'Bindings & Consumers' in content
    assert "x-data=\"integrationWorkspaceTabs(" in content
    assert "x-on:popstate.window=\"syncTab()\"" in content
    assert 'integration_workspace_tabs.js' in read('app/templates/layouts/app.html')
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })); } } }" not in content


def test_alertmanager_configuration_uses_shared_side_decision_and_primary_form_workspace():
    content = read('app/templates/alertmanager/partials/_detail_configuration.html')
    shared = read('app/templates/integrations/components/_configuration_decision.html')
    assert 'configuration_decision.side_panel(' in content
    assert 'Alertmanager Configuration Decision' in content
    assert 'Alertmanager API v2' in content
    assert 'Controlled Flow' in shared
    assert 'data-kaori-configuration-decision-side' in shared
    assert 'grid-cols-[minmax(0,1fr)_25rem]' in content
    assert 'xl:sticky xl:top-4' in shared


def test_alertmanager_validation_uses_kubernetes_style_capability_readiness_and_registry():
    content = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    registry = read('app/templates/alertmanager/partials/_capability_registry.html')
    assert 'Alertmanager Capability Readiness' in content
    assert "integrations/components/_capability_readiness.html" in content
    assert 'data-kaori-provider-capability-matrix' in content
    assert 'Validation Decision' not in content
    assert 'Alert Management Capability Registry' in registry
    assert 'record_actions.view_more(' in registry
    assert 'table_ui.table_classes' in registry


def test_alertmanager_runtime_uses_kubernetes_layout_and_history_filters():
    panel = read('app/templates/alertmanager/partials/_runtime_panel.html')
    history = read('app/templates/alertmanager/partials/_runtime_history.html')
    assert "integrations/components/_runtime_decision.html" in panel
    assert 'runtime_decision.render(' in panel
    assert 'Runtime Evidence' in panel
    assert 'data-kaori-alertmanager-runtime-evidence' in panel
    assert 'step.summary' in panel
    assert 'lg:sticky' not in panel
    assert 'xl:sticky' not in panel
    assert 'runtime_history_filters_enabled = true' in history


def test_alertmanager_bindings_use_standard_table_and_native_dialog():
    content = read('app/templates/alertmanager/partials/_detail_scope.html')
    assert 'Bindings &amp; Consumers' in content
    assert 'Bound Operational Scopes' in content
    assert 'Effective Consumer Resolution' in content
    assert 'Binding Decision' in content
    assert '<dialog id="alertmanager-create-binding-dialog"' in content
    assert 'table_ui.table_classes' in content


def test_alertmanager_runtime_history_accepts_server_side_filters():
    routes = read('app/alertmanager/routes.py')
    presentation = read('app/alertmanager/presentation.py')
    assert "history_trigger = request.args.get('history_trigger'" in routes
    assert "history_health = request.args.get('history_health'" in routes
    assert "history_readiness = request.args.get('history_readiness'" in routes
    assert 'trigger_type: str = \'\'' in presentation
    assert 'health_status: str = \'\'' in presentation
    assert 'readiness: str = \'\'' in presentation
