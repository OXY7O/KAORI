from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_front_pages_share_one_canonical_hierarchy() -> None:
    templates = {
        'kubernetes': read('app/templates/integrations/kubernetes.html'),
        'metrics_source': read('app/templates/integrations/metrics.html'),
        'alertmanager': read('app/templates/integrations/alertmanager.html'),
        'minio': read('app/templates/minio/index.html'),
    }

    for provider, template in templates.items():
        assert 'integrations/components/_provider_frontpage.html' in template, provider
        assert 'components/integration_workspace_tabs.html' in template, provider
        assert 'provider_front.hero(' in template, provider
        assert 'provider_front.overview(' in template, provider
        assert 'integration_tabs.render(' in template, provider


def test_shared_overview_owns_summary_and_boundary_geometry() -> None:
    overview = read('app/templates/integrations/components/_provider_frontpage.html')

    assert 'data-kaori-provider-frontpage-hero' in overview
    assert 'Registered Connections' in overview
    assert 'Ready Connections' in overview
    assert 'Consumer Bindings' in overview
    assert 'Register Connection' in overview
    assert 'data-kaori-provider-integration-overview' in overview
    assert 'integration_ui.metric_grid_classes(4)' in overview
    assert 'Integration Contract' in overview
    assert 'Consumer Resolution' in overview
    assert 'Authority Boundary' in overview
    assert 'md:grid-cols-3' in overview


def test_kubernetes_frontpage_uses_same_coverage_and_registry_contract() -> None:
    page = read('app/templates/integrations/kubernetes.html')
    coverage = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    routes = read('app/integrations/routes.py')
    frontpage_service = read('app/integrations/kubernetes_frontpage.py')

    assert 'Kubernetes Integration Overview' in page
    assert 'integration_tabs.render("kubernetes"' in page
    assert '{% include "integrations/kubernetes/partials/_integration_coverage.html" %}' in page
    assert '{% include "integrations/kubernetes/partials/_registry.html" %}' in page
    assert 'provider_registry.asset_coverage_head(' in coverage
    assert 'Kubernetes Cluster' in coverage
    assert 'Kubernetes API' in coverage
    assert 'provider_registry.connection_registry_head()' in registry
    assert '<input type="hidden" name="tab" value="registry">' in registry
    assert "target == 'kubernetes-integration-coverage'" in routes
    assert "request.args.get('coverage_q', '')" in routes
    kubernetes_builder = frontpage_service.split('def build_kubernetes_page', 1)[1]
    assert "'coverage_rows': coverage_page_rows" in kubernetes_builder
    assert "'coverage_pagination': coverage_pagination" in kubernetes_builder


def test_minio_empty_and_populated_states_keep_registry_geometry() -> None:
    index = read('app/templates/minio/index.html')
    coverage = read('app/templates/minio/partials/_coverage.html')
    coverage_content = read('app/templates/minio/partials/_coverage_content.html')
    registry = read('app/templates/minio/partials/_registry.html')
    registry_content = read('app/templates/minio/partials/_registry_content.html')
    routes = read('app/minio/routes.py')
    presentation = read('app/minio/presentation.py')

    assert 'MinIO Integration Overview' in index
    assert '{% include "minio/partials/_coverage.html" %}' in index
    assert '{% include "minio/partials/_registry.html" %}' in index

    assert 'minio-coverage-filter-form' in coverage
    assert 'minio-coverage-content' in coverage
    assert 'minio-registry-filter-form' in registry
    assert 'minio-registry-content' in registry

    for content in (coverage_content, registry_content):
        assert 'provider_registry.' in content
        assert '_table_classes()' in content
        assert 'components/states/_empty_state.html' in content
        assert 'provider_registry.pagination_footer(' in content

    assert "target == 'minio-coverage-content'" in routes
    assert "target == 'minio-registry-content'" in routes
    assert 'coverage_query:' in presentation
    assert 'compatibility:' in presentation


def test_provider_connection_registries_share_one_column_contract() -> None:
    registry_component = read('app/templates/integrations/components/_provider_registry.html')
    registries = [
        read('app/templates/integrations/kubernetes/partials/_registry.html'),
        read('app/templates/integrations/metrics/partials/_inventory_content.html'),
        read('app/templates/integrations/alertmanager/partials/_inventory_content.html'),
        read('app/templates/minio/partials/_registry_content.html'),
    ]

    for label in ('Connection', 'Endpoint / Scope', 'Core Readiness', 'Compatibility', 'Bindings', 'Actions'):
        assert label in registry_component
    for template in registries:
        assert 'provider_registry.connection_registry_colgroup()' in template
        assert 'provider_registry.connection_registry_head()' in template


def test_asset_provider_coverage_tables_share_one_column_contract() -> None:
    registry_component = read('app/templates/integrations/components/_provider_registry.html')
    kubernetes = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')
    minio = read('app/templates/minio/partials/_coverage_content.html')

    for label in ('Metrics Source', 'Alert Source', 'Coverage', 'Actions'):
        assert label in registry_component
    assert 'provider_registry.asset_coverage_head(' in kubernetes
    assert 'Kubernetes Cluster' in kubernetes
    assert 'Kubernetes API' in kubernetes
    assert 'provider_registry.asset_coverage_head(' in minio
    assert 'Object Storage Asset' in minio
    assert 'MinIO API' in minio


def test_observability_coverage_includes_kubernetes_and_object_storage_assets() -> None:
    coverage_service = read('app/integrations/coverage.py')
    coverage_template = read('app/templates/components/integration_coverage_content.html')
    consumer_assets = read('app/integrations/consumer_assets.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')

    assert 'registered_consumer_asset_definitions()' in coverage_service
    assert 'integration_taxonomy_document()' in consumer_assets
    assert 'asset_type: kubernetes_cluster' in taxonomy_catalog
    assert 'asset_type: object_storage_system' in taxonomy_catalog
    assert 'for definition in registered_consumer_asset_definitions()' in coverage_service
    assert 'Choose Source' in coverage_template
    assert 'Manage Binding' in coverage_template
    assert 'url_for(provider.registry_endpoint' in coverage_template
