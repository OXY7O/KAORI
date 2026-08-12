from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_front_pages_share_one_canonical_hierarchy() -> None:
    templates = {
        'kubernetes': read('app/templates/integrations/kubernetes.html'),
        'prometheus': read('app/templates/integrations/prometheus.html'),
        'alertmanager': read('app/templates/integrations/alertmanager.html'),
        'minio': read('app/templates/minio/index.html'),
    }

    for provider, template in templates.items():
        assert 'integrations/components/_provider_frontpage.html' in template, provider
        assert 'components/integration_workspace_tabs.html' in template, provider
        assert 'Operational Integration' in template, provider
        assert 'Registered Connections' in template, provider
        assert 'Ready Connections' in template, provider
        assert 'Consumer Bindings' in template, provider
        assert 'Register Connection' in template, provider
        assert 'provider_front.overview(' in template, provider
        assert 'integration_tabs.render(' in template, provider


def test_shared_overview_owns_summary_and_boundary_geometry() -> None:
    overview = read('app/templates/integrations/components/_provider_frontpage.html')

    assert 'data-kaori-provider-integration-overview' in overview
    assert 'integration_ui.metric_grid_classes(4)' in overview
    assert 'Integration Contract' in overview
    assert 'Consumer Resolution' in overview
    assert 'Authority Boundary' in overview
    assert 'md:grid-cols-3' in overview


def test_kubernetes_specialized_readiness_stays_inside_coverage_tab() -> None:
    page = read('app/templates/integrations/kubernetes.html')
    coverage = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/service.py')

    assert 'Kubernetes Integration Overview' in page
    assert 'integration_tabs.render("kubernetes"' in page
    assert '{% include "integrations/kubernetes/partials/_integration_coverage.html" %}' in page
    assert '{% include "integrations/kubernetes/partials/_registry.html" %}' in page
    assert 'Operational Readiness Paths' in coverage
    assert '<input type="hidden" name="tab" value="registry">' in registry
    assert "'tab': 'registry'" in registry
    assert "context['active_tab']" in routes
    assert "request.args.get('tab', 'coverage')" in routes
    kubernetes_builder = service.split('def build_kubernetes_page', 1)[1].split(
        'def build_kubernetes_capability_registry', 1
    )[0]
    assert "'active_tab'" not in kubernetes_builder


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
        assert 'table_ui.table_classes(' in content
        assert 'components/states/_empty_state.html' in content
        assert 'provider_registry.pagination_footer(' in content

    assert "target == 'minio-coverage-content'" in routes
    assert "target == 'minio-registry-content'" in routes
    assert 'coverage_query:' in presentation
    assert 'compatibility:' in presentation
