from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_taxonomy_owns_domain_workspace_routes() -> None:
    taxonomy = read('app/integrations/taxonomy.py')

    assert 'workspace_endpoint: str' in taxonomy
    assert "workspace_endpoint='integrations.orchestration'" in taxonomy
    assert "workspace_endpoint='integrations.observability'" in taxonomy
    assert "workspace_endpoint='integrations.storage'" in taxonomy


def test_sidebar_navigation_is_domain_driven_not_product_driven() -> None:
    navigation = read('app/integrations/navigation.py')
    sidebar = read('app/templates/components/navigation/integrations_menu.html')

    assert 'for module in registry.all()' in navigation
    assert 'module.navigation_endpoint_prefixes' in navigation
    assert 'active_domain_key = module.domain_key' in navigation
    assert "provider_type == 'kubernetes'" not in navigation
    assert "provider_type == 'prometheus'" not in navigation
    assert "provider_type == 'alertmanager'" not in navigation

    assert 'integration_navigation.domains' in sidebar
    assert 'url_for(domain.workspace_endpoint)' in sidebar
    assert '{{ domain.label }}' in sidebar
    assert "url_for('integrations.kubernetes')" not in sidebar
    assert "url_for('integrations.prometheus')" not in sidebar
    assert "url_for('integrations.alertmanager')" not in sidebar


def test_builtin_providers_declare_domain_navigation_ownership() -> None:
    expected = {
        'app/integrations/kubernetes/__init__.py': "navigation_endpoint_prefixes=('integrations.kubernetes', 'cluster.')",
        'app/integrations/prometheus/__init__.py': "navigation_endpoint_prefixes=('integrations.prometheus', 'prometheus.')",
        'app/integrations/alertmanager/__init__.py': "navigation_endpoint_prefixes=('integrations.alertmanager', 'alertmanager.')",
    }
    for relative, marker in expected.items():
        assert marker in read(relative)


def test_domain_landing_routes_share_one_taxonomy_page_builder() -> None:
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/service.py')

    assert 'def _render_domain_page(domain_key: str)' in routes
    assert "@integrations_bp.get('/orchestration')" in routes
    assert "@integrations_bp.get('/observability')" in routes
    assert "@integrations_bp.get('/storage')" in routes
    assert "'integrations/domain.html'" in routes
    assert 'build_integration_domain_page(domain_key)' in routes

    builder = service.split('def build_integration_domain_page', 1)[1].split(
        'def _kubernetes_readiness', 1
    )[0]
    assert 'get_domain_definition(domain_key)' in builder
    assert 'for module in registry.all() if module.domain_key == domain.key' in builder
    assert 'IntegrationInstance.query.options(selectinload(IntegrationInstance.bindings))' in builder
    assert 'IntegrationInstance.provider_type.in_(provider_types)' in builder
    assert 'capability_definitions_for_domain(domain.key)' in builder
    assert "'bindings': bindings" in builder
    assert "'status': status" in builder
    assert 'KubernetesConnection.query' not in builder
    assert 'PrometheusInstance.query' not in builder
    assert 'AlertmanagerInstance.query' not in builder


def test_domain_template_uses_kaori_hero_capability_and_provider_boundaries() -> None:
    template = read('app/templates/integrations/domain.html')

    assert 'components/page_hero.html' in template
    assert 'integrations/components/_workspace.html' in template
    assert 'Capability Portfolio' in template
    assert 'Provider Workspaces' in template
    assert 'No {{ domain.label }} Provider Registered' in template
    assert 'Ready for provider registration' in template
    assert 'Register Provider' in template
    assert 'Validate Runtime' in template
    assert 'Bind Assets' in template
    assert 'rounded-lg border border-outline-subtle bg-surface-hover px-3 py-3' not in template
    assert 'url_for(item.workspace_endpoint)' in template
    assert 'Domain Operating Boundary' in template
    assert 'data-kaori-integration-domain-workspace' in template
    assert '{{ integration_ui.section_header(' in template
    assert '{% call integration_ui.section_header(' not in template
    assert 'lg:grid-cols-2' not in template
    assert 'raw Tailwind' not in template


def test_breadcrumbs_insert_domain_between_integrations_and_provider() -> None:
    navigation = read('app/common/navigation.py')

    assert "BreadcrumbItem('Orchestration')" in navigation
    assert "BreadcrumbItem('Observability')" in navigation
    assert "'integrations.orchestration': 'Orchestration'" in navigation
    assert "'integrations.observability': 'Observability'" in navigation
    assert "'integrations.storage': 'Storage'" in navigation
