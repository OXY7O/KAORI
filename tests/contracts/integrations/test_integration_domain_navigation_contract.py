from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_taxonomy_owns_domain_workspace_routes_and_asset_ownership() -> None:
    taxonomy = read('app/integrations/taxonomy.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')

    assert 'workspace_endpoint: str' in taxonomy
    assert 'asset_types: tuple[str, ...] = ()' in taxonomy
    assert 'workspace_endpoint: integrations.orchestration' in taxonomy_catalog
    assert 'workspace_endpoint: integrations.observability' in taxonomy_catalog
    assert 'workspace_endpoint: integrations.storage' in taxonomy_catalog
    assert '- kubernetes_cluster' in taxonomy_catalog
    assert '- object_storage_system' in taxonomy_catalog
    assert 'integration_taxonomy_document()' in taxonomy
    assert 'def asset_types_for_domain(domain_key: str)' in taxonomy
    assert 'def domain_key_for_asset_type(asset_type: str)' in taxonomy


def test_sidebar_navigation_is_domain_driven_not_product_driven() -> None:
    navigation = read('app/integrations/navigation.py')
    sidebar = read('app/templates/components/navigation/integrations_menu.html')

    assert 'for module in registry.all()' in navigation
    assert 'module.navigation_endpoint_prefixes' in navigation
    assert 'active_domain_key = module.domain_key' in navigation
    assert "provider_type == 'kubernetes'" not in navigation
    assert "provider_type == 'prometheus'" not in navigation
    assert "provider_type == 'alertmanager'" not in navigation
    assert "provider_type == 'minio'" not in navigation

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
        'app/integrations/minio/__init__.py': "navigation_endpoint_prefixes=('minio.',)",
    }
    for relative, marker in expected.items():
        assert marker in read(relative)


def test_domain_landing_routes_share_one_taxonomy_page_builder() -> None:
    routes = read('app/integrations/routes.py')
    domain_service = read('app/integrations/domain_service.py')

    assert 'def _render_domain_page(domain_key: str)' in routes
    assert "@integrations_bp.get('/orchestration')" in routes
    assert "@integrations_bp.get('/observability')" in routes
    assert "@integrations_bp.get('/storage')" in routes
    assert "'integrations/domain.html'" in routes
    assert 'build_integration_domain_page(' in routes
    assert "active_tab=request.args.get('tab', 'registry').strip()" in routes
    assert "per_page=request.args.get('provider_per_page', 5, type=int) or 5" in routes
    assert "per_page=request.args.get('binding_per_page', 5, type=int) or 5" in routes

    assert 'build_integration_domain_page' in routes
    assert 'ProviderRegistryFilters' in routes
    assert 'BindingRegistryFilters' in routes
    assert 'get_domain_definition(domain_key)' in domain_service
    assert 'for module in registry.all() if module.domain_key == domain.key' in domain_service
    assert 'IntegrationInstance.query.filter(IntegrationInstance.provider_type.in_(provider_types))' in domain_service
    assert 'IntegrationInstance.provider_type.in_(provider_types)' in domain_service
    assert 'asset_types_for_domain(domain_key)' in domain_service
    assert 'IntegrationBinding.asset_type.in_(owned_asset_types)' in domain_service
    assert 'domain_key_for_asset_type(binding.asset_type)' in domain_service
    assert 'selector_summary(binding.selector_json' in domain_service
    assert 'paginate_sequence(' in domain_service
    assert "'bindings': sum(1 for binding in consumer_bindings if binding.enabled)" in domain_service
    assert (
        'consumer_bindings = [binding for binding in related_bindings if not _is_owner_asset_binding(binding)]'
        in domain_service
    )
    assert 'module.domain_key == owner_domain' in domain_service
    assert '_consumer_binding_count(instance, consumer_bindings)' in domain_service
    assert 'KubernetesConnection.query' not in domain_service
    assert 'PrometheusInstance.query' not in domain_service
    assert 'AlertmanagerInstance.query' not in domain_service
    assert 'MinioInstance.query' not in domain_service


def test_domain_template_uses_shared_capability_registry_provider_registry_and_bindings() -> None:
    template = read('app/templates/integrations/domain.html')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    content_tabs = read('app/templates/components/content_tabs.html')

    assert 'components/page_hero.html' in template
    assert 'integrations/partials/_domain_workspace.html' in template
    assert 'components/content_tabs.html' in workspace
    assert 'components/pagination.html' in workspace
    assert 'components/table.html' in workspace
    assert 'components/table_registry.html' in workspace
    assert 'Capability Registry' in template
    assert 'Provider Registry' in workspace
    assert 'Consumer Bindings' in workspace
    assert 'Registry and Consumer Bindings' in workspace
    assert 'Registry and Bindings' not in workspace
    assert 'data-kaori-domain-provider-registry' in workspace
    assert 'data-kaori-domain-binding-registry' in workspace
    assert 'No {{ domain.label }} Provider Registered' in workspace
    assert 'No {{ domain.label }} Consumer Bindings Yet' in workspace
    assert 'Core Validation' in template
    assert 'Consumer Contract' in workspace
    assert 'url_for(row.workspace_endpoint)' in workspace
    assert 'Open {{ item.runtime_label }}' in workspace
    assert 'hx_target="#domain-workspace"' in workspace
    assert 'hx_select="#domain-workspace"' in workspace
    assert 'hx_indicator="#integration-domain-workspace-loading"' in workspace
    assert 'hx_indicator=none' in content_tabs
    assert 'hx-indicator="{{ hx_indicator }}"' in content_tabs
    assert 'Domain Operating Boundary' in template
    assert 'data-kaori-integration-domain-workspace' in template
    assert 'provider_registry_pagination.allowed_per_page' in workspace
    assert 'binding_registry_pagination.allowed_per_page' in workspace
    assert 'Clear Filters' not in workspace or 'clear_filters_link' in workspace
    assert '{% call integration_ui.section_header(' not in template
    assert '{{ integration_ui.section_header(' in template


def test_domain_binding_registry_is_cross_domain_and_asset_centric() -> None:
    taxonomy = read('app/integrations/taxonomy.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    domain_service = read('app/integrations/domain_service.py')
    template = read('app/templates/integrations/partials/_domain_workspace.html')

    assert 'integration_taxonomy_document()' in taxonomy
    assert '- kubernetes_cluster' in taxonomy_catalog
    assert '- object_storage_system' in taxonomy_catalog
    assert 'IntegrationInstance.provider_type.in_(provider_types)' in domain_service
    assert 'IntegrationBinding.asset_type.in_(owned_asset_types)' in domain_service
    assert 'or_(*clauses)' in domain_service
    assert 'Native Provider Contract' not in domain_service
    assert 'Native Provider Contract' not in template
    assert 'Consumer Profile Pending' in domain_service
    assert '_is_owner_asset_binding(binding)' in domain_service
    assert (
        'Native provider ownership is represented by the Provider Registry and is not duplicated as a consumer binding.'
        in template
    )


def test_breadcrumbs_insert_domain_between_integrations_and_provider() -> None:
    navigation = read('app/common/navigation.py')
    integration_navigation = read('app/integrations/navigation.py')
    presentation = read('app/bootstrap/presentation.py')

    assert 'integration_endpoint_owner(request.endpoint)' in presentation
    assert 'integration_owner=integration_owner' in presentation
    assert 'integration_owner: Mapping[str, str] | None = None' in navigation
    assert "BreadcrumbItem(integration_owner['domain_label'])" in navigation
    assert "BreadcrumbItem(integration_owner['provider_label'])" in navigation
    assert "'integrations.orchestration': 'Orchestration'" in navigation
    assert "'integrations.observability': 'Observability'" in navigation
    assert "'integrations.storage': 'Storage'" in navigation
    assert "'domain_label': module.domain.label" in integration_navigation
