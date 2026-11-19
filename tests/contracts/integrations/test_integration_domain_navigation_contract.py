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
    assert 'workspace_endpoint: integrations.registry' in taxonomy_catalog
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
    assert "provider_type == '" not in navigation
    assert "provider_type == 'alertmanager'" not in navigation
    assert "provider_type == 'minio'" not in navigation

    assert 'integration_navigation.domains' in sidebar
    assert 'url_for(domain.workspace_endpoint)' in sidebar
    assert '{{ domain.label }}' in sidebar
    assert "url_for('integrations.kubernetes')" not in sidebar
    assert "url_for('integrations.metrics_sources')" not in sidebar
    assert "url_for('integrations.alertmanager')" not in sidebar


def test_builtin_providers_declare_domain_navigation_ownership() -> None:
    expected = {
        'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/__init__.py': "navigation_endpoint_prefixes=('integrations.kubernetes', 'cluster.')",
        'app/integrations/observability/metrics_source/__init__.py': "navigation_endpoint_prefixes=('integrations.metrics_sources', 'metrics.')",
        'app/integrations/observability/alert_source/providers/alertmanager/__init__.py': "navigation_endpoint_prefixes=('integrations.alertmanager', 'alertmanager.')",
        'app/integrations/storage/object_storage/providers/minio/__init__.py': "navigation_endpoint_prefixes=('minio.',)",
        'app/integrations/registry/providers/harbor/__init__.py': "navigation_endpoint_prefixes=('harbor.',)",
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
    assert "@integrations_bp.get('/registry')" in routes
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
    assert (
        'IntegrationInstance.query.filter(IntegrationInstance.integration_type.in_(integration_types))'
        in domain_service
    )
    assert 'IntegrationInstance.integration_type.in_(integration_types)' in domain_service
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
    assert 'MetricsSource.query' not in domain_service
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


def test_all_six_integration_domains_share_an_icon_free_workspace_introduction() -> None:
    domain = read('app/templates/integrations/domain.html')
    partial = read('app/templates/integrations/partials/_domain_workspace.html')
    shared = read('app/templates/integrations/components/_workspace.html')
    provider_tabs = read('app/templates/components/integration_workspace_tabs.html')
    routes = read('app/integrations/routes.py')

    # The outer introduction precedes the card, but is outside the HTMX
    # partial replaced by tab/filter/pagination operations.
    assert 'data-kaori-domain-workspace-section' in domain
    assert 'integration_ui.workspace_section_intro(' in domain
    assert 'domain.label ~ " Providers & Connections"' in domain
    assert '"Review Source Control provider readiness and registered connections."' in domain
    assert '"Review provider readiness, connections, and governed consumer bindings."' in domain
    assert 'domain.key == "source_control"' in domain
    assert domain.index('integration_ui.workspace_section_intro(') < domain.index(
        '{% include "integrations/partials/_domain_workspace.html" %}'
    )
    assert 'id="domain-workspace"' in partial
    assert 'hx_target="#domain-workspace"' in partial
    assert 'hx_select="#domain-workspace"' in partial
    assert 'workspace_section_intro(' not in partial

    # Domain and provider pages share the exact already-approved icon-free
    # semantic markup rather than independent provider-specific headers.
    assert 'integration_ui.workspace_section_intro(' in provider_tabs
    assert 'macro workspace_section_intro(title, description, aria_label)' in shared
    intro_macro = shared.split('macro workspace_section_intro', 1)[1].split('{%- endmacro %}', 1)[0]
    assert '<header class="min-w-0 px-1" aria-label="{{ aria_label }}">' in intro_macro
    assert 'palette_icon(' not in intro_macro
    for route in (
        '/orchestration',
        '/observability',
        '/storage',
        '/registry',
        '/secrets-management',
        '/source-control',
    ):
        assert route in routes


def test_domain_provider_open_is_read_first_and_add_is_registration_only() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    domain_service = read('app/integrations/domain_service.py')
    tabs = read('app/templates/components/integration_workspace_tabs.html')

    assert 'url_for(item.workspace_endpoint)' in workspace
    assert 'Open {{ item.runtime_label }}' in workspace
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace
    assert 'Add Connection' in workspace
    assert 'aria-label="{{ item.runtime_label }} navigation"' in workspace
    assert 'Review GitHub App installations and committed repository evidence.' in workspace
    assert "'workspace_endpoint': module.workspace_endpoint" in domain_service
    assert 'integration_ui.section_header(' in tabs
    assert '"Integration Workspace"' in tabs
    assert '"Switch between integration coverage and registered connections."' in tabs
    assert 'Provider Connections & Coverage' in tabs
    # #4544 removed the redundant inner Workspace Guide. That legacy
    # assertion was invalid even though source and navigation were correct.
    assert 'title_extra=workspace_guide' not in tabs
    assert 'info_tip.render(' not in tabs


def test_domain_binding_registry_is_cross_domain_and_asset_centric() -> None:
    taxonomy = read('app/integrations/taxonomy.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    domain_service = read('app/integrations/domain_service.py')
    template = read('app/templates/integrations/partials/_domain_workspace.html')

    assert 'integration_taxonomy_document()' in taxonomy
    assert '- kubernetes_cluster' in taxonomy_catalog
    assert '- object_storage_system' in taxonomy_catalog
    assert 'IntegrationInstance.integration_type.in_(integration_types)' in domain_service
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
    assert "'integrations.registry': 'Registry'" in navigation
    assert "'domain_label': module.domain.label" in integration_navigation


def test_provider_sidebar_uses_registry_owner_not_default_overview(monkeypatch) -> None:
    """Breadcrumb and sidebar must agree for provider and instance endpoints."""

    from types import SimpleNamespace

    from app.common import workspace_navigation as sidebar
    from app.integrations.navigation import integration_endpoint_owner

    monkeypatch.setattr(sidebar, 'url_for', lambda endpoint, **_kwargs: f'/{endpoint}')
    monkeypatch.setattr(sidebar, 'local_super_admin', lambda _user: False)
    user = SimpleNamespace(
        is_authenticated=True,
        has_permission=lambda permission: permission == 'integrations.manage',
    )

    def active_keys(endpoint: str, override: str | None = None) -> list[str]:
        sections = sidebar.build_sidebar_navigation(endpoint, user, active_capability_override=override)
        workspace = next(item for section in sections for item in section['items'] if item['key'] == 'integrations')
        assert workspace['active']
        return [child['key'] for child in workspace['children'] if child['active']]

    provider_routes = {
        'integrations.metrics_sources': 'observability',
        'integrations.alertmanager': 'observability',
        'metrics.instance_detail': 'observability',
        'alertmanager.instance_detail': 'observability',
        'integrations.kubernetes': 'orchestration',
        'minio.index': 'storage',
        'harbor.index': 'registry',
        'vault.index': 'secrets_management',
        'github_source.index': 'source_control',
    }
    for endpoint, expected in provider_routes.items():
        owner = integration_endpoint_owner(endpoint)
        assert owner is not None, endpoint
        assert owner['domain_key'] == expected, endpoint
        assert active_keys(endpoint, owner['domain_key']) == [expected], endpoint

    assert active_keys('integrations.overview') == ['overview']
    assert active_keys('integrations.observability') == ['observability']
    assert active_keys('integrations.choose_integration_provider', 'observability') == ['observability']

    # Unknown selector ownership must not arbitrarily activate an unavailable capability.
    assert active_keys('integrations.choose_integration_provider', 'invalid-domain') == ['overview']


def test_presentation_reuses_provider_owner_for_sidebar_and_breadcrumb() -> None:
    presentation = read('app/bootstrap/presentation.py')
    sidebar = read('app/common/workspace_navigation.py')

    assert 'integration_owner = integration_endpoint_owner(request.endpoint)' in presentation
    assert (
        "active_integration_domain_key = integration_owner['domain_key'] if integration_owner else None" in presentation
    )
    assert "active_integration_domain_key = selector_domain['key']" in presentation
    assert 'active_capability_override=active_integration_domain_key' in presentation
    assert 'integration_owner=integration_owner' in presentation
    assert "workspace.key == 'integrations'" in sidebar
    assert 'active_workspace == workspace.key' in sidebar
    assert 'active_capability_override in {capability.key for capability in visible_capabilities}' in sidebar


def test_registry_domain_consumer_bindings_project_asset_owned_observability_sources() -> None:
    """Registry owns registry_instance assets; cross-domain sources remain independent."""

    from app.integrations.taxonomy import asset_types_for_domain, domain_key_for_asset_type

    assert asset_types_for_domain('registry') == ('registry_instance',)
    assert domain_key_for_asset_type('registry_instance') == 'registry'
    assert domain_key_for_asset_type('kubernetes_cluster') == 'orchestration'
    assert domain_key_for_asset_type('object_storage_system') == 'storage'

    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    registry_capability = taxonomy_catalog.split('- key: registry\n  domain_key: registry\n', 1)[1].split(
        '\n- key: secrets_pki', 1
    )[0]
    assert '  asset_types:\n  - registry_instance' in registry_capability
    assert '- asset_type: registry_instance' in taxonomy_catalog
    assert '  integration_type: registry' in taxonomy_catalog

    domain_service = read('app/integrations/domain_service.py')
    related = domain_service.split('def _load_related_bindings(', 1)[1].split('def _integration_type_rows(', 1)[0]
    assert 'owned_asset_types = asset_types_for_domain(domain_key)' in related
    assert 'IntegrationInstance.integration_type.in_(integration_types)' in related
    assert 'IntegrationBinding.asset_type.in_(owned_asset_types)' in related
    assert '.filter(or_(*clauses))' in related

    # The existing domain flow loads the provider and owned-asset evidence
    # together, but never counts native provider ownership as a consumer.
    owner_filter = (
        'consumer_bindings = [binding for binding in related_bindings if not _is_owner_asset_binding(binding)]'
    )
    assert owner_filter in domain_service
    assert "'bindings': sum(1 for binding in consumer_bindings if binding.enabled)" in domain_service
    assert 'all_binding_rows = _binding_registry_rows(' in domain_service
    assert 'filtered_binding_rows = _filter_binding_rows(' in domain_service
    assert 'binding_registry_rows, binding_pagination = paginate_sequence(' in domain_service

    registry_observability = read('app/integrations/registry/observability.py')
    harbor_presentation = read('app/integrations/registry/providers/harbor/application/presentation.py')
    harbor_service = read('app/integrations/registry/providers/harbor/application/service.py')
    assert "IntegrationBinding.asset_type == 'registry_instance'" in registry_observability
    assert "IntegrationInstance.integration_type == 'metrics_source'" in registry_observability
    assert "asset_type='registry_instance'" in harbor_presentation
    assert "'asset_type': 'registry_instance'" in harbor_service
    assert "'asset_key': str(canonical.id)" in harbor_service
