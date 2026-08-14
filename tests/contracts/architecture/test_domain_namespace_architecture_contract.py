from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_and_analytics_use_explicit_domain_namespaces() -> None:
    assert (ROOT / 'app/inventory/kubernetes').is_dir()
    assert (ROOT / 'app/inventory/object_storage').is_dir()
    assert (ROOT / 'app/analytics/kubernetes').is_dir()
    assert (ROOT / 'app/analytics/object_storage').is_dir()
    assert (ROOT / 'app/analytics/shared').is_dir()

    for retired in (
        'app/storage_inventory',
        'app/inventory/resources',
        'app/inventory/collectors',
        'app/analytics/common',
        'app/analytics/storage',
        'app/analytics/capacity',
    ):
        assert not (ROOT / retired).exists(), retired


def test_object_storage_analytics_domain_is_metrics_backend_neutral() -> None:
    service = read('app/analytics/object_storage/service.py')
    contracts = read('app/analytics/shared/metrics/contracts.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')
    resolver = read('app/analytics/object_storage/sources/resolver.py')

    assert 'class MetricsSource(Protocol)' in contracts
    assert 'PrometheusConsumer' not in service
    assert 'PrometheusError' not in service
    assert 'get_object_storage_query_expression' not in service
    assert 'PrometheusConsumer' in adapter
    assert 'retry_count=0' in adapter
    assert '_SOURCE_ADAPTERS' in resolver
    assert "metrics_provider='prometheus'" in resolver
    assert "asset_profile='minio-v2'" in resolver


def test_retired_object_storage_prometheus_domain_modules_are_deleted() -> None:
    assert not (ROOT / 'app/analytics/object_storage/metrics.py').exists()
    assert not (ROOT / 'app/analytics/object_storage/parsing.py').exists()


def test_platform_operations_category_uses_distinct_workspace_name() -> None:
    menu = read('app/templates/components/navigation/platform_operations_menu.html')
    overview = read('app/templates/platform_operations/overview/index.html')
    assert 'Operations Center' in menu
    assert 'Operations Center' in overview

def test_integration_binding_service_has_no_domain_compatibility_wrapper() -> None:
    binding_service = read('app/integrations/binding_service.py')
    routes = read('app/integrations/routes.py')

    assert 'def create_cluster_source_binding(' not in binding_service
    assert 'def cluster(self)' not in binding_service
    assert 'create_source_binding(' in routes
    assert 'SourceBindingSpec(' in routes
    assert "asset_type='kubernetes_cluster'" in routes
