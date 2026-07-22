from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_retired_integration_http_facade_is_removed() -> None:
    assert not (ROOT / 'app/integrations/legacy_routes.py').exists()
    application = read('app/__init__.py')
    assert 'legacy_integrations_bp' not in application


def test_provider_form_facades_are_removed() -> None:
    alertmanager_forms = read('app/alertmanager/forms.py')
    prometheus_service = read('app/prometheus/service.py')
    assert 'AlertmanagerConfigForm' not in alertmanager_forms
    assert 'parse_alertmanager_config_form' not in alertmanager_forms
    assert 'def save_config(' not in prometheus_service
    assert 'PrometheusConfigForm' not in prometheus_service


def test_cluster_does_not_store_kubernetes_provider_runtime_state() -> None:
    cluster_model = read('app/models/cluster.py')
    for field in (
        'kubernetes_version',
        'kubernetes_platform',
        'kubernetes_compatibility_status',
        'kubernetes_compatibility_profile',
        'kubernetes_readiness_status',
        'kubernetes_lifecycle_status',
        'kubernetes_api_discovery_summary',
        'kubernetes_validation_message',
        'kubernetes_last_validated_at',
    ):
        assert field not in cluster_model


def test_kubernetes_connection_owns_runtime_contract() -> None:
    connection_model = read('app/models/kubernetes.py')
    for field in (
        'detected_version',
        'detected_platform',
        'compatibility_status',
        'compatibility_profile',
        'readiness_status',
        'lifecycle_status',
        'validation_message',
        'last_validated_at',
        'discovery_summary',
    ):
        assert field in connection_model
