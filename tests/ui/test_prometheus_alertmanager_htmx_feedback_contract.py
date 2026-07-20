from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROM_ROUTES = ROOT / 'app/prometheus/routes.py'
ALERT_ROUTES = ROOT / 'app/alertmanager/routes.py'
PROM_TEMPLATES = ROOT / 'app/templates/prometheus'
ALERT_TEMPLATES = ROOT / 'app/templates/alertmanager'
SHARED_FEEDBACK = ROOT / 'app/templates/components/operation_feedback_oob.html'
STANDARD = ROOT / 'docs/design/components/OPERATIONAL_ACTION_FEEDBACK.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_shared_feedback_persists_audit_and_uses_oob_toast() -> None:
    component = read(SHARED_FEEDBACK)
    service = read(ROOT / 'app/notifications/service.py')
    assert "toast_oob=true" in component
    assert "_quick_sync_result.html" in component
    assert 'persist_notification(' in service
    assert 'def record_operational_activity(' in service


def test_prometheus_normal_mutations_use_htmx_and_oob_feedback() -> None:
    registration = read(PROM_TEMPLATES / 'instance_form.html')
    configuration = read(PROM_TEMPLATES / 'partials/_detail_configuration.html')
    validation = read(PROM_TEMPLATES / 'partials/_detail_validation_content.html')
    runtime = read(PROM_TEMPLATES / 'partials/_runtime_panel.html')
    runtime_response = read(PROM_TEMPLATES / 'partials/_runtime_refresh_response.html')
    scope = read(PROM_TEMPLATES / 'partials/_detail_scope.html')
    modal = read(PROM_TEMPLATES / 'partials/_delete_confirmation_modal.html')

    assert 'hx-post="{{ url_for(\'prometheus.new_instance\'' in registration
    assert 'hx-target="#prometheus-registration-workspace"' in registration
    assert 'hx-post="{{ url_for(\'prometheus.instance_detail\'' in configuration
    assert 'hx-target="#prometheus-configuration-workspace"' in configuration
    assert 'hx-post="{{ url_for(\'prometheus.instance_validate\'' in validation
    assert 'hx-post="{{ url_for(\'prometheus.refresh_runtime\'' in runtime
    assert 'hx-post="{{ url_for(\'prometheus.add_instance_binding\'' in scope
    assert 'hx-target="#prometheus-scope-workspace"' in modal
    assert "form.setAttribute('hx-post', deleteUrl)" in modal
    assert "form.addEventListener('htmx:afterRequest', closeModal)" in modal
    for source in (registration, configuration, validation, runtime_response, scope):
        assert 'operation_feedback_oob.html' in source


def test_alertmanager_normal_mutations_use_htmx_and_oob_feedback() -> None:
    registration = read(ALERT_TEMPLATES / 'instance_form.html')
    configuration = read(ALERT_TEMPLATES / 'partials/_detail_configuration.html')
    validation = read(ALERT_TEMPLATES / 'partials/_detail_validation_content.html')
    runtime = read(ALERT_TEMPLATES / 'partials/_runtime_panel.html')
    runtime_response = read(ALERT_TEMPLATES / 'partials/_runtime_refresh_response.html')
    scope = read(ALERT_TEMPLATES / 'partials/_detail_scope.html')
    modal = read(ALERT_TEMPLATES / 'partials/_delete_confirmation_modal.html')

    assert 'hx-post="{{ url_for(\'alertmanager.new_instance\'' in registration
    assert 'hx-target="#alertmanager-registration-workspace"' in registration
    assert 'hx-post="{{ url_for(\'alertmanager.instance_detail\'' in configuration
    assert 'hx-target="#alertmanager-configuration-workspace"' in configuration
    assert 'hx-post="{{ url_for(\'alertmanager.validate_instance\'' in validation
    assert 'hx-post="{{ url_for(\'alertmanager.refresh_runtime\'' in runtime
    assert 'hx-post="{{ url_for(\'alertmanager.create_binding\'' in scope
    assert 'hx-target="#alertmanager-scope-workspace"' in modal
    assert "form.setAttribute('hx-post', deleteUrl)" in modal
    assert "form.addEventListener('htmx:afterRequest', closeModal)" in modal
    for source in (registration, configuration, validation, runtime_response, scope):
        assert 'operation_feedback_oob.html' in source


def test_provider_routes_record_all_normal_action_outcomes() -> None:
    prom = read(PROM_ROUTES)
    alert = read(ALERT_ROUTES)
    for event in (
        'prometheus_instance_created',
        'prometheus_instance_create_rejected',
        'prometheus_instance_create_failed',
        'prometheus_instance_updated',
        'prometheus_instance_update_rejected',
        'prometheus_instance_update_failed',
        'prometheus_connection_test',
        'prometheus_connection_test_failed',
        'prometheus_compatibility_validation',
        'prometheus_runtime_refreshed',
        'prometheus_runtime_refresh_failed',
        'prometheus_binding_created',
        'prometheus_binding_create_rejected',
        'prometheus_binding_create_failed',
        'prometheus_binding_deleted',
        'prometheus_binding_delete_failed',
        'prometheus_instance_deleted',
        'prometheus_instance_delete_rejected',
        'prometheus_instance_delete_failed',
    ):
        assert event in prom
    for event in (
        'alertmanager_instance_created',
        'alertmanager_instance_create_rejected',
        'alertmanager_instance_create_failed',
        'alertmanager_instance_updated',
        'alertmanager_instance_update_rejected',
        'alertmanager_instance_update_failed',
        'alertmanager_connection_test',
        'alertmanager_connection_test_failed',
        'alertmanager_instance_validated',
        'alertmanager_instance_validation_failed',
        'alertmanager_runtime_refreshed',
        'alertmanager_runtime_refresh_failed',
        'alertmanager_binding_created',
        'alertmanager_binding_create_rejected',
        'alertmanager_binding_create_failed',
        'alertmanager_binding_deleted',
        'alertmanager_binding_delete_failed',
        'alertmanager_instance_deleted',
        'alertmanager_instance_delete_rejected',
        'alertmanager_instance_delete_failed',
    ):
        assert event in alert
    assert '_htmx_redirect(location)' in prom
    assert '_htmx_redirect(location)' in alert


def test_standard_documents_same_page_and_navigation_contracts() -> None:
    standard = read(STANDARD)
    for phrase in (
        'Every action must produce one user-visible toast and one durable Activity Audit record',
        'The page is not fully reloaded',
        'HX-Redirect',
        'Cluster compatibility routes may exist only as redirect or migration boundaries',
    ):
        assert phrase in standard
