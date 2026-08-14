from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_analytics_keeps_provider_credentials_outside_analytics() -> None:
    service = read('app/analytics/object_storage/service.py')
    metrics = read('app/analytics/object_storage/metrics.py')

    assert 'PrometheusConsumer.for_asset' in service
    assert "scope_type='object_storage_system'" in service
    assert 'ObjectStorageSystem' in service
    for token in ('MinioClient', 'MinioInstance', 'secret_key', 'access_key', 'boto3'):
        assert token not in service
        assert token not in metrics


def test_object_storage_analytics_exposes_kubernetes_style_surface_set() -> None:
    routes = read('app/analytics/routes.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')

    for endpoint in (
        'object_storage_overview',
        'object_storage_capacity',
        'object_storage_performance',
        'object_storage_forecast',
        'object_storage_top_consumers',
        'object_storage_alerts',
    ):
        assert f"endpoint='{endpoint}'" in routes
        assert f"analytics.{endpoint}" in menu


def test_object_storage_alertmanager_is_optional_and_evidence_boundaries_are_explicit() -> None:
    service = read('app/analytics/object_storage/service.py')
    boundary = read('app/templates/analytics/object_storage/partials/_evidence_boundary.html')

    assert 'Alertmanager is optional for this release' in service
    assert 'Committed Inventory' in boundary
    assert 'Operational Time-Series' in boundary
    assert 'Lifecycle Correlation · Deferred' in boundary


def test_prometheus_transport_capability_ownership_is_provider_core() -> None:
    resolver = read('app/prometheus/resolver.py')

    assert 'def _available_technical_capabilities' in resolver
    assert 'provider_payload = instance.capabilities or {}' in resolver
    assert 'binding_payload = binding.validation_evidence or {}' in resolver
    assert 'observed = _available_technical_capabilities(binding, instance)' in resolver
