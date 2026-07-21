from __future__ import annotations

from pathlib import Path

from app.integrations.registry import registry

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_builtin_integrations_register_independent_modules() -> None:
    modules = {module.provider_type: module for module in registry.all()}
    assert set(modules) == {'kubernetes', 'prometheus', 'alertmanager'}
    for provider, module in modules.items():
        assert module.module_path == f'app.integrations.{provider}'
        assert module.operations
        assert module.capability_keys
        assert module.compatibility_profiles
        assert all(module.queue_for(operation) for operation in module.operations)
        assert 'client.build' in module.operations
        assert module.queue_for('client.build') == 'inline'


def test_provider_module_contract_files_and_readmes_exist() -> None:
    required = {
        'kubernetes': {'adapter.py', 'client.py', 'capabilities.py', 'validation.py', 'discovery.py', 'inventory.py', 'actions.py', 'schemas.py', 'README.md'},
        'prometheus': {'adapter.py', 'client.py', 'capabilities.py', 'validation.py', 'queries.py', 'evidence.py', 'schemas.py', 'README.md'},
        'alertmanager': {'adapter.py', 'client.py', 'capabilities.py', 'validation.py', 'alerts.py', 'silences.py', 'schemas.py', 'README.md'},
    }
    for provider, files in required.items():
        root = ROOT / 'app/integrations' / provider
        assert files.issubset({path.name for path in root.iterdir()})


def test_domain_services_call_registry_instead_of_transport_facades() -> None:
    for path in (
        'app/inventory/service.py',
        'app/kubernetes_operations/configmaps/service.py',
        'app/kubernetes_operations/secrets/live_service.py',
        'app/governance/tls_certificates/collector.py',
        'app/prometheus/service.py',
        'app/prometheus/consumer.py',
        'app/alertmanager/service.py',
    ):
        source = read(path)
        assert 'get_integration(' in source, path
        assert 'KubernetesClient(' not in source, path
        assert 'PrometheusClient(' not in source, path
        assert 'AlertmanagerClient(' not in source, path


def test_legacy_provider_urls_are_redirect_only() -> None:
    source = read('app/integrations/legacy_routes.py')
    assert '@legacy_integrations_bp.get' in source
    assert '@legacy_integrations_bp.post' not in source
    assert '@legacy_integrations_bp.route' not in source
    assert "response.headers['Deprecation'] = 'true'" in source
    assert "response.headers['Sunset']" in source
    assert 'test_connection(' not in source
    assert 'enqueue_' not in source


def test_provider_routes_do_not_register_cluster_scoped_operations() -> None:
    prometheus = read('app/prometheus/routes.py')
    alertmanager = read('app/alertmanager/routes.py')
    assert "'/cluster/<string:cluster_id>" not in prometheus
    assert "'/cluster/<string:cluster_id>" not in alertmanager
    assert not (ROOT / 'app/templates/prometheus/config.html').exists()
    assert not (ROOT / 'app/templates/alertmanager/config.html').exists()


def test_canonical_models_have_single_binding_and_credential_authority() -> None:
    cluster = read('app/models/cluster.py')
    integration = read('app/models/integration.py')
    kubernetes = read('app/models/kubernetes.py')
    prometheus = read('app/models/prometheus.py')
    alertmanager = read('app/models/alertmanager.py')

    assert "__tablename__ = 'integration_bindings'" in integration
    assert "__tablename__ = 'prometheus_bindings'" not in prometheus
    assert "__tablename__ = 'alertmanager_bindings'" not in alertmanager
    assert 'kubeconfig:' not in cluster
    assert 'kubeconfig:' in kubernetes
    assert 'EncryptedText' in kubernetes
    assert 'EncryptedText' in prometheus
    assert 'EncryptedText' in alertmanager


def test_module_map_documents_scalability_boundaries() -> None:
    module_map = read('docs/architecture/integration-module-map.md')
    assert 'Route / Celery Task' in module_map
    assert 'Integration Registry' in module_map
    assert 'Celery Beat dispatches schedules only' in module_map
    assert 'Do not add a second binding table' in module_map


def test_retired_python_provider_facades_are_removed() -> None:
    retired = (
        'app/kubernetes',
        'app/prometheus/client.py',
        'app/prometheus/capabilities.py',
        'app/prometheus/query_profiles',
        'app/prometheus/runtime_adapter.py',
        'app/alertmanager/client.py',
        'app/alertmanager/capabilities.py',
        'app/alertmanager/normalizers',
        'app/alertmanager/profiles',
        'app/alertmanager/runtime_adapter.py',
        'app/models/integration_runtime.py',
        'app/integrations/runtime/kubernetes_adapter.py',
    )
    for path in retired:
        assert not (ROOT / path).exists(), path
