from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_runtime_adapter_validates_instance_directly() -> None:
    source = _read('app/prometheus/runtime_adapter.py')
    assert 'PrometheusService(instance).validate_integration()' in source
    assert 'instance.bindings' not in source.split('def refresh', 1)[1].split('def get_state', 1)[0]


def test_prometheus_service_accepts_standalone_instance() -> None:
    source = _read('app/prometheus/service.py')
    assert 'source: Cluster | PrometheusInstance' in source
    assert 'self.instance = config' in source


def test_prometheus_configuration_uses_instance_operations() -> None:
    source = _read('app/templates/prometheus/config.html')
    assert "prometheus.instance_test" in source
    assert "prometheus.instance_validate" in source
    assert "prometheus.test_connection" not in source
    assert "prometheus.validate_integration" not in source


def test_runtime_history_refresh_is_instance_scoped() -> None:
    source = _read('app/templates/prometheus/partials/_runtime_history.html')
    assert "prometheus.instance_runtime_history" in source
