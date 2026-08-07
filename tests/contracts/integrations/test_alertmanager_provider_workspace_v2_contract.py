from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_alertmanager_detail_uses_provider_v2_tabs_without_malformed_alpine_markup():
    content = read('app/templates/alertmanager/instance_detail.html')
    assert 'Bindings & Consumers' in content
    assert "x-on:popstate.window=\"syncTabFromLocation()\"" in content
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })); } } }" not in content


def test_alertmanager_configuration_uses_connection_contract_and_decision_panel():
    content = read('app/templates/alertmanager/partials/_detail_configuration.html')
    assert 'Alertmanager Connection Contract' in content
    assert 'Alertmanager API v2' in content
    assert 'Configuration Decision' in content
    assert 'Controlled Flow' in content
    assert 'h-10 w-full' in content


def test_alertmanager_validation_uses_capability_registry_and_decision_panel():
    content = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    assert 'Alert Management Capability Registry' in content
    assert 'Validation Decision' in content
    assert 'Operational Domains' in content
    assert 'View More' in content
    assert 'table_ui.table_classes' in content


def test_alertmanager_runtime_uses_horizontal_runtime_decision_and_history_filters():
    panel = read('app/templates/alertmanager/partials/_runtime_panel.html')
    history = read('app/templates/alertmanager/partials/_runtime_history.html')
    assert 'Runtime Decision' in panel
    assert 'Runtime Evidence' in panel
    assert 'Primary Finding' in panel
    assert 'Evidence Boundary' in panel
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
