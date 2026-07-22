from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_runtime_adapter_validates_instance_directly() -> None:
    source = _read('app/integrations/prometheus/adapter.py')
    assert 'PrometheusService(instance).validate_integration()' in source
    assert "operation == 'client.build'" in source
    assert 'instance.bindings' not in source.split('def refresh', 1)[1].split('def get_state', 1)[0]


def test_prometheus_service_accepts_standalone_instance() -> None:
    source = _read('app/prometheus/service.py')
    assert 'source: Cluster | PrometheusInstance' in source
    assert 'self.instance = config' in source


def test_prometheus_cluster_configuration_template_is_removed() -> None:
    assert not Path('app/templates/prometheus/config.html').exists()


def test_prometheus_instance_detail_uses_instance_operations() -> None:
    routes = _read('app/prometheus/routes.py')
    assert "@prometheus_bp.post('/instances/<int:instance_id>/test')" in routes
    assert "@prometheus_bp.post('/instances/<int:instance_id>/validate')" in routes


def test_runtime_history_refresh_is_instance_scoped() -> None:
    source = _read('app/templates/prometheus/partials/_detail_runtime.html')
    assert "prometheus.instance_runtime_history" in source
