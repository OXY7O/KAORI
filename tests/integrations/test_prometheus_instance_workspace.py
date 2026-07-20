from pathlib import Path


def test_prometheus_workspace_exposes_create_route_and_instance_inventory():
    routes = Path('app/prometheus/routes.py').read_text()
    service = Path('app/integrations/service.py').read_text()
    template = Path('app/templates/integrations/prometheus.html').read_text()

    assert "'/instances/new'" in routes
    assert 'def new_instance()' in routes
    assert 'save_prometheus_instance' in routes
    assert 'PrometheusInstance.query.order_by' in service
    assert "url_for('prometheus.new_instance')" in template


def test_kubernetes_workspace_exposes_prometheus_binding_actions():
    service = Path('app/integrations/service.py').read_text()
    template = Path('app/templates/integrations/kubernetes/partials/_registry.html').read_text()

    assert "'prometheus_instance_id': prometheus.id if prometheus else None" in service
    assert "url_for('integrations.bind_prometheus_source', scope_key=row.cluster_id)" in template
    assert "url_for('prometheus.instance_detail', instance_id=row.prometheus_instance_id)" in template
    assert "url_for('integrations.bind_alertmanager_source', scope_key=row.cluster_id)" in template
    assert "url_for('alertmanager.instance_detail', instance_id=row.alertmanager_instance_id)" in template
