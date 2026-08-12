from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_minio_index_uses_canonical_provider_registry_shell() -> None:
    index = read('app/templates/minio/index.html')
    tabs = read('app/templates/components/integration_workspace_tabs.html')
    registry = read('app/templates/minio/partials/_registry_content.html')

    assert 'MinIO Integrations' in index
    assert 'provider_front.hero(' in index
    assert 'Register Connection' in read('app/templates/integrations/components/_provider_frontpage.html')
    assert 'MinIO Integration Overview' in index
    assert 'integration_workspace_tabs' in index
    assert 'Integration Coverage' in tabs
    assert 'Connection Registry' in tabs
    assert 'No MinIO Connections Found' in registry


def test_minio_registration_matches_shared_connection_workflow() -> None:
    form = read('app/templates/minio/instance_form.html')

    assert 'Register MinIO Connection' in form
    assert 'Connection Configuration' in form
    assert 'Test Connection' in form
    assert 'Register Connection' in form
    assert 'grid-cols-12' in form
    assert 'xl:col-span-8' in form
    assert 'xl:col-span-4' in form
    assert 'connectionVerified' in form


def test_minio_detail_uses_same_four_provider_workspace_domains() -> None:
    detail = read('app/templates/minio/instance_detail.html')

    assert 'x-data="integrationWorkspaceTabs(' in detail
    assert 'framed_workspace_tabs.render' in detail
    for label in ('Configuration', 'Validation & Capabilities', 'Runtime & History', 'Bindings & Lifecycle'):
        assert label in detail
    assert 'MinIO Integration' in detail
    assert 'Connection Posture' in detail


def test_minio_bindings_expose_metrics_and_alert_consumer_profiles() -> None:
    scope = read('app/templates/minio/partials/_detail_scope.html')
    binding_registry = read('app/templates/minio/partials/_binding_registry.html')
    validation = read('app/templates/minio/partials/_detail_validation.html')

    assert 'Consumer Binding Registry' in binding_registry
    assert 'Prometheus Metrics Consumer' in scope
    assert 'Alertmanager Alert Consumer' in scope
    assert 'minio-metrics-2024-v1' in scope
    assert 'minio-alerts-v1' in scope
    assert 'Compatibility & Capability Matrix' in validation
    assert 'MinIO Capability Readiness' in validation
    assert 'Capability Registry' in read('app/templates/minio/partials/_capability_registry.html')
    assert 'consumer-specific evidence' in validation.lower()


def test_minio_detail_matches_asset_owner_lifecycle_contract() -> None:
    detail = read('app/templates/minio/instance_detail.html')
    configuration = read('app/templates/minio/partials/_detail_configuration.html')
    scope = read('app/templates/minio/partials/_detail_scope.html')
    runtime = read('app/templates/minio/partials/_detail_runtime.html')
    modal = read('app/templates/minio/partials/_delete_modal.html')
    shared_modal = read('app/templates/integrations/components/_asset_owner_delete_modal.html')
    tabs_js = read('app/static/js/integration_workspace_tabs.js')

    assert 'MinIO API Readiness' in detail
    assert 'Validated Capabilities' in detail
    assert 'Bindings & Lifecycle' in detail
    assert 'minio/partials/_delete_modal.html' in detail
    assert 'Configure Connection' in configuration
    assert "url_for('minio.edit_instance'" in configuration
    assert 'Connection Lifecycle' in scope
    assert 'Delete Connection' in scope
    assert "url_for('minio.delete_instance'" in scope
    assert 'asset_owner_delete_modal.render(' in modal
    assert 'This action cannot be undone.' in shared_modal
    assert 'openDelete(url, name)' in tabs_js
    assert 'Refresh Runtime' in runtime
    assert "url_for('minio.refresh_runtime'" in runtime


def test_minio_asset_owner_deletion_removes_asset_bindings_not_shared_sources() -> None:
    service = read('app/minio/service.py')
    routes = read('app/minio/routes.py')
    deletion = read('app/integrations/deletion.py')

    assert 'def delete_minio_instance(' in service
    assert 'asset_owner_deletion_guard(' in service
    assert 'IntegrationBinding.asset_type == OBJECT_STORAGE_SYSTEM_SCOPE' in service
    assert 'db.session.delete(asset)' in service
    assert "provider_type='minio'" in service
    assert 'Prometheus and Alertmanager source instances remain reusable' in service
    assert "@minio_bp.post('/instances/<int:instance_id>/delete')" in routes
    assert 'def asset_owner_deletion_guard(' in deletion
    assert 'JobExecution.scope_type == asset_type' in deletion


def test_minio_configuration_and_runtime_have_provider_parity_routes() -> None:
    routes = read('app/minio/routes.py')
    workspace_web = read('app/minio/workspace_web.py')
    form = read('app/templates/minio/instance_form.html')
    service = read('app/minio/service.py')

    assert "@minio_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])" in routes
    assert 'def update_minio_instance(' in service
    assert 'Leave blank to keep the current secret key' in read('app/minio/forms.py')
    assert 'Edit MinIO Connection' in form
    assert 'Save Changes' in form
    assert "url_for('minio.test_instance_configuration'" in form
    assert "@minio_bp.post('/instances/<int:instance_id>/runtime/refresh')" in routes
    assert 'queue_runtime_refresh(' in routes
    assert 'enqueue_runtime_health_refresh(' in workspace_web
    assert 'runtime_refresh_status' in routes


def test_minio_validation_runtime_and_binding_tables_match_kubernetes_workspace_contract() -> None:
    detail = read('app/templates/minio/instance_detail.html')
    validation = read('app/templates/minio/partials/_detail_validation.html')
    capability_registry = read('app/templates/minio/partials/_capability_registry.html')
    runtime = read('app/templates/minio/partials/_detail_runtime.html')
    bindings = read('app/templates/minio/partials/_binding_registry.html')
    routes = read('app/minio/routes.py')

    assert 'Validation & Capabilities' in detail
    assert 'connection_validation_header.render(' in validation
    assert "hx-post=\"{{ url_for('minio.validate_instance'" in validation
    assert 'minio-validation-loading' in validation
    assert "hx-get=\"{{ url_for('minio.validation_status'" in validation
    assert 'minio-capability-registry' in capability_registry
    assert 'capability_per_page' in capability_registry
    assert 'pagination_ui.numeric_pages(' in capability_registry
    assert 'hx-target="#minio-capability-registry"' in capability_registry
    assert 'integrations/partials/_runtime_history.html' in runtime
    assert 'runtime_history_filters_enabled=true' in runtime
    assert 'minio.runtime_history' in runtime
    assert 'minio-binding-registry' in bindings
    assert 'binding_per_page' in bindings
    assert 'pagination_ui.numeric_pages(' in bindings
    assert 'hx-target="#minio-binding-registry"' in bindings
    assert "@minio_bp.get('/instances/<int:instance_id>/capabilities/registry')" in routes
    assert "@minio_bp.get('/instances/<int:instance_id>/runtime/history')" in routes
    assert "@minio_bp.get('/instances/<int:instance_id>/bindings/registry')" in routes
