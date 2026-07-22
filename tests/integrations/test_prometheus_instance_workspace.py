from pathlib import Path


def test_prometheus_workspace_exposes_canonical_create_route_and_inventory_owner():
    routes = Path('app/prometheus/routes.py').read_text()
    repository = Path('app/prometheus/repository.py').read_text()
    template = Path('app/templates/integrations/prometheus.html').read_text()

    assert "'/instances/new'" in routes
    assert 'def new_instance()' in routes
    assert 'save_prometheus_instance' in routes
    assert 'def list_instances(' in repository
    assert 'PrometheusInstance.query.order_by' in repository
    assert "url_for('prometheus.new_instance')" in template


def test_kubernetes_registry_and_binding_workspaces_have_single_owners():
    service = Path('app/integrations/service.py').read_text()
    registry = Path('app/templates/integrations/kubernetes/partials/_registry.html').read_text()
    routes = Path('app/integrations/routes.py').read_text()

    assert "'prometheus_instance_id': prometheus.id if prometheus else None" in service
    assert "'alertmanager_instance_id': alertmanager.id if alertmanager else None" in service
    assert "@integrations_bp.route('/prometheus/bind', methods=['GET', 'POST'])" in routes
    assert "@integrations_bp.route('/alertmanager/bind', methods=['GET', 'POST'])" in routes
    assert "url_for('integrations.kubernetes_detail', cluster_id=row.cluster_id)" in registry
    assert "url_for('integrations.bind_prometheus_source'" not in registry
    assert "url_for('integrations.bind_alertmanager_source'" not in registry
