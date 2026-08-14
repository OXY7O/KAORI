from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_analytics_domain_is_metrics_backend_neutral() -> None:
    service = read('app/analytics/object_storage/service.py')
    resolver = read('app/analytics/object_storage/sources/resolver.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')
    contracts = read('app/analytics/shared/metrics/contracts.py')

    assert 'MetricsSource' in service
    assert 'resolve_object_storage_metrics_source' in service
    assert 'PrometheusConsumer' not in service
    assert 'PrometheusError' not in service
    assert 'query_profiles.prometheus' not in service
    assert '_SOURCE_ADAPTERS' in resolver
    assert "metrics_provider='prometheus'" in resolver
    assert "asset_profile='minio-v2'" in resolver
    assert 'MinioPrometheusMetricsSource.supports' in resolver
    assert 'PrometheusConsumer.for_asset' in adapter
    assert "scope_type='object_storage_system'" in adapter
    assert 'retry_count=0' in adapter
    assert 'class MetricsSource(Protocol)' in contracts

    for token in ('MinioClient', 'MinioInstance', 'secret_key', 'access_key', 'boto3'):
        assert token not in service
        assert token not in contracts


def test_prometheus_payload_parsing_is_owned_by_adapter_not_domain_service() -> None:
    service = read('app/analytics/object_storage/service.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')

    assert '_vector_scalar' in adapter
    assert '_vector_by_label' in adapter
    assert '_matrix_points' in adapter
    assert "payload.get('data')" not in service
    assert not (ROOT / 'app/analytics/object_storage/parsing.py').exists()
    assert not (ROOT / 'app/analytics/object_storage/metrics.py').exists()


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
        assert f'analytics.{endpoint}' in menu


def test_object_storage_alertmanager_is_optional_and_evidence_boundaries_are_explicit() -> None:
    service = read('app/analytics/object_storage/service.py')
    boundary = read('app/templates/analytics/object_storage/partials/_evidence_boundary.html')

    assert 'Alertmanager is optional for this release' in service
    assert 'Committed Inventory' in boundary
    assert 'Operational Time-Series' in boundary
    assert 'Lifecycle Correlation · Deferred' in boundary
    assert 'metrics_source.provider_label' in boundary


def test_metrics_source_transport_failure_is_request_fail_fast() -> None:
    service = read('app/analytics/object_storage/service.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')

    assert 'source_wide_failure' in service
    assert 'if self.source_wide_failure is not None' in service
    assert 'if exc.source_wide' in service
    assert 'retry_count=0' in adapter


def test_prometheus_transport_capability_ownership_is_provider_core() -> None:
    resolver = read('app/prometheus/resolver.py')

    assert 'def _available_technical_capabilities' in resolver
    assert 'provider_payload = instance.capabilities or {}' in resolver
    assert 'binding_payload = binding.validation_evidence or {}' in resolver
    assert 'observed = _available_technical_capabilities(binding, instance)' in resolver
