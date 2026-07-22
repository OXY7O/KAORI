from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_binding_validation_worker_uses_registry_contract():
    worker = (ROOT / 'app/integrations/validation/tasks.py').read_text(encoding='utf-8')

    assert 'from app.prometheus.service import validate_prometheus_binding' not in worker
    assert 'from app.alertmanager.service import' not in worker
    assert "execute_integration_operation(" in worker
    assert "'binding.validate'" in worker
    assert 'module.get_instance(instance_id)' in worker


def test_provider_modules_publish_binding_validation_operation():
    for relative in (
        'app/integrations/prometheus/__init__.py',
        'app/integrations/alertmanager/__init__.py',
    ):
        source = (ROOT / relative).read_text(encoding='utf-8')
        assert "'binding.validate': 'integration-validation'" in source
        assert "'binding.validate'," in source


def test_provider_adapters_own_binding_validation_dispatch():
    prometheus = (ROOT / 'app/integrations/prometheus/adapter.py').read_text(encoding='utf-8')
    alertmanager = (ROOT / 'app/integrations/alertmanager/adapter.py').read_text(encoding='utf-8')

    assert "if operation == 'binding.validate':" in prometheus
    assert 'validate_prometheus_binding' in prometheus
    assert "if operation == 'binding.validate':" in alertmanager
    assert 'validate_alertmanager_binding' in alertmanager


def test_integration_routes_do_not_query_provider_models_directly():
    routes = (ROOT / 'app/integrations/routes.py').read_text(encoding='utf-8')

    forbidden = (
        'KubernetesConnection.query',
        'PrometheusInstance.query',
        'AlertmanagerInstance.query',
        'Cluster.query',
        'from app.models import AlertmanagerInstance',
        'from app.models.kubernetes import KubernetesConnection',
    )
    for token in forbidden:
        assert token not in routes


def test_binding_creation_is_owned_by_domain_service():
    routes = (ROOT / 'app/integrations/routes.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/integrations/binding_service.py').read_text(encoding='utf-8')

    assert 'create_cluster_source_binding(' in routes
    assert 'create_prometheus_binding(' not in routes
    assert 'add_alertmanager_binding(' not in routes
    assert 'def create_cluster_source_binding(' in service
    assert 'create_prometheus_binding(' in service
    assert 'add_alertmanager_binding(' in service
