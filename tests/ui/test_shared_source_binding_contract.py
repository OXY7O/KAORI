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


def test_legacy_negative_coverage_templates_are_removed() -> None:
    assert not (ROOT / 'app/templates/components/uncovered_operational_scopes.html').exists()
    assert not (ROOT / 'app/templates/integrations/partials/_table.html').exists()


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


def test_transitional_unscoped_status_is_removed_from_runtime_contract() -> None:
    coverage = read('app/integrations/coverage.py')
    migration = read('migrations/versions/20260722_foundation_compatibility_cleanup.py')
    resolvers = read('app/prometheus/resolver.py') + read('app/alertmanager/resolver.py')

    assert 'legacy_unscoped' not in coverage
    assert "validation_status == 'legacy_unscoped'" in migration
    assert 'legacy_unscoped' not in resolvers
    assert "validation_status='validation_required'" in migration

def test_binding_selector_can_be_reconfigured_in_place_for_both_providers() -> None:
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
