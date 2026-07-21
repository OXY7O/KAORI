from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_bind_first_workspaces_are_available_for_both_providers() -> None:
    routes = read('app/integrations/routes.py')
    workspace = read('app/templates/integrations/bindings/partials/_workspace.html')

    assert "@integrations_bp.route('/prometheus/bind', methods=['GET', 'POST'])" in routes
    assert "@integrations_bp.route('/alertmanager/bind', methods=['GET', 'POST'])" in routes
    assert 'Bind Existing {{ provider.label }} Source' in workspace
    assert 'Reuse one registered connection across multiple scopes.' in workspace
    assert 'Register New Connection' in workspace
    assert 'selector_label' in workspace
    assert 'selector_value' in workspace


def test_shared_source_isolation_is_applied_at_consumer_boundaries() -> None:
    prometheus_client = read('app/integrations/prometheus/client.py')
    prometheus_consumer = read('app/prometheus/consumer.py')
    alertmanager_consumer = read('app/alertmanager/consumer.py')

    assert 'apply_promql_scope' in prometheus_client
    assert 'scope_selector=self.binding.selector_json' in prometheus_consumer
    assert '_merge_alert_query(query, candidate.binding.selector_json)' in alertmanager_consumer
    assert 'selector_filters(candidate.binding.selector_json)' in alertmanager_consumer


def test_binding_validation_routes_enqueue_dedicated_worker_jobs() -> None:
    prom_routes = read('app/prometheus/routes.py')
    alert_routes = read('app/alertmanager/routes.py')
    tasks = read('app/integrations/validation/tasks.py')
    prom_scope = read('app/templates/prometheus/partials/_detail_scope.html')
    alert_scope = read('app/templates/alertmanager/partials/_detail_scope.html')

    assert 'def validate_instance_binding(' in prom_routes
    assert "enqueue_binding_validation(\n            provider_type='prometheus'" in prom_routes
    assert 'def validate_binding(instance_id: int, binding_id: int)' in alert_routes
    assert "enqueue_binding_validation(\n            provider_type='alertmanager'" in alert_routes
    assert 'validate_prometheus_binding(instance=instance, binding=binding)' in tasks
    assert 'validate_alertmanager_binding(instance=instance, binding=binding)' in tasks
    assert "url_for('prometheus.validate_instance_binding'" in prom_scope
    assert "url_for('alertmanager.validate_binding'" in alert_scope
    assert 'hx-trigger="load delay:1500ms"' in prom_scope
    assert 'hx-trigger="load delay:1500ms"' in alert_scope


def test_legacy_negative_coverage_templates_are_removed() -> None:
    assert not (ROOT / 'app/templates/components/uncovered_operational_scopes.html').exists()
    assert not (ROOT / 'app/templates/integrations/partials/_table.html').exists()


def test_binding_validation_is_an_operational_resolution_gate() -> None:
    prom_resolver = read('app/prometheus/resolver.py')
    alert_resolver = read('app/alertmanager/resolver.py')

    for resolver in (prom_resolver, alert_resolver):
        assert "_ELIGIBLE_BINDING_VALIDATION" in resolver
        assert "{'ready', 'legacy_unscoped'}" in resolver
        assert 'binding_validation_eligible' in resolver
        assert 'Validate the scope selector before operational use.' in resolver


def test_binding_workspace_blocks_provider_sources_with_blocked_readiness() -> None:
    coverage = read('app/integrations/coverage.py')
    workspace = read('app/templates/integrations/bindings/partials/_workspace.html')

    assert "blocked_readiness = {'blocked', 'unavailable', 'disabled', 'incompatible'}" in coverage
    assert "'selectable': selectable" in coverage
    assert 'Registered sources are not eligible for a new binding' in workspace


def test_alertmanager_bindings_advertise_the_v2_capabilities_consumers_request() -> None:
    bindings = read('app/alertmanager/bindings.py')

    for capability in ('alerts_v2', 'silences_v2', 'status_v2'):
        assert f"'{capability}'" in bindings


def test_legacy_unscoped_source_cannot_be_shared_until_selector_replacement() -> None:
    coverage = read('app/integrations/coverage.py')
    migration = read('migrations/versions/20260720_binding_selectors.py')

    assert 'unscoped_counts' in coverage
    assert 'legacy_unscoped_count == 0' in coverage
    assert 'Replace existing legacy unscoped bindings' in coverage
    assert "validation_status = 'legacy_unscoped'" in migration


def test_legacy_binding_selector_can_be_configured_in_place_for_both_providers() -> None:
    prom_routes = read('app/prometheus/routes.py')
    alert_routes = read('app/alertmanager/routes.py')
    prom_service = read('app/prometheus/service.py')
    alert_service = read('app/alertmanager/service.py')
    prom_scope = read('app/templates/prometheus/partials/_detail_scope.html')
    alert_scope = read('app/templates/alertmanager/partials/_detail_scope.html')

    assert "bindings/<int:binding_id>/selector" in prom_routes
    assert "bindings/<int:binding_id>/selector" in alert_routes
    assert 'def update_prometheus_binding_selector(' in prom_service
    assert 'def update_alertmanager_binding_selector(' in alert_service
    assert "url_for('prometheus.update_instance_binding_selector'" in prom_scope
    assert "url_for('alertmanager.update_binding_selector'" in alert_scope
    for service in (prom_service, alert_service):
        assert "binding.validation_status = 'validation_required'" in service
        assert 'binding.last_validated_at = None' in service
