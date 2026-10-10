import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _navigation_source() -> str:
    return _read('app/common/workspace_navigation.py') + '\n' + _read('app/common/workspace_navigation_catalog.py')


def _tenant_service_source() -> str:
    return '\n'.join(
        _read(path)
        for path in (
            'app/kubernetes/tenant/service.py',
            'app/kubernetes/tenant/service_contracts.py',
            'app/kubernetes/tenant/registry_context.py',
            'app/kubernetes/tenant/resource_profile_controls.py',
        )
    )


def _tenant_discovery_source() -> str:
    return (
        _read('app/kubernetes/tenant/discovery_service.py')
        + '\n'
        + _read('app/kubernetes/tenant/discovery_adoption.py')
    )


def test_tenant_is_a_kubernetes_sidebar_capability_under_v21() -> None:
    model = _navigation_source()
    sidebar = (ROOT / 'app/templates/components/navigation/sidebar.html').read_text(encoding='utf-8')

    assert "key='kubernetes'" in model
    assert "'tenant', 'Tenant', 'building-2', 'tenant.index'" in model
    assert 'data-kaori-sidebar-capability="{{ child[\'key\'] }}"' in sidebar



def test_tenant_generated_credential_material_preserves_tenants_navigation_and_breadcrumb() -> None:
    workspace_navigation = _read('app/common/workspace_navigation.py')
    breadcrumb_source = _read('app/common/navigation.py')
    sidebar_tenant = _read('app/templates/components/navigation/tenant_menu.html')
    route = _read('app/kubernetes/tenant/routes_credentials.py')
    material = _read('app/templates/kubernetes/tenant/credential_material.html')

    assert "'tenant.generate_credential_material_route': 'tenants'" in workspace_navigation
    assert "'tenant.generate_credential_material_route': 'Access Material'" in breadcrumb_source
    assert "request.endpoint in ['tenant.tenants', 'tenant.tenant_detail', 'tenant.generate_credential_material_route']" in sidebar_tenant
    assert "def generate_credential_material_route(credential_id: int):" in route
    assert "tenant_page='tenants'" in route
    assert "data-kaori-hero-profile=\"transactional-admin\"" in material
    assert "page_hero.shell_classes()" in material
    assert "{% block dashboard_content %}" in material
    assert "{% block tenant_content %}" not in material


def test_tenant_routes_own_only_five_primary_destinations() -> None:
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    for path, endpoint in (
        ('/tenants', 'tenants'),
        ('/resource-profiles', 'resource_profiles'),
        ('/namespace-provisioning', 'namespace_provisioning'),
        ('/operations', 'operations'),
    ):
        assert f"@tenant_bp.get('{path}')" in routes
        assert f'def {endpoint}()' in routes

    for template in (
        'kubernetes/tenant/overview.html',
        'kubernetes/tenant/tenants.html',
        'kubernetes/tenant/resource_profiles.html',
        'kubernetes/tenant/namespace_provisioning.html',
        'kubernetes/tenant/operations.html',
    ):
        assert template in routes

    get_routes = set(re.findall(r"@tenant_bp\.get\('([^']+)'\)", routes))
    primary_routes = {'/', '/tenants', '/resource-profiles', '/namespace-provisioning', '/operations'}
    assert primary_routes.issubset(get_routes)
    assert '/overview/cluster-estate' in get_routes
    assert '/tenants/registry' not in get_routes
    assert '/tenants/membership-registry' not in get_routes
    assert '/tenants/group-registry' not in get_routes
    assert {'/management', '/inventory', '/analytics'}.isdisjoint(get_routes)


def test_tenant_pages_reuse_kaori_shared_presentation_patterns() -> None:
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    operations = (ROOT / 'app/templates/kubernetes/tenant/operations.html').read_text(encoding='utf-8')

    assert 'components/page_hero.html' in base
    assert 'page_hero.intro' in base
    assert 'page_hero.context_card' in base
    assert 'components/content_tabs.html' in operations
    assert 'content_tabs.render_links' in operations

    for label in ('Provisioning', 'Runs & Evidence', 'Allocation Drift', 'Operational Reconcile', 'Activity'):
        assert label in operations

    for path in (
        'overview.html',
        'tenants.html',
        'resource_profiles.html',
        'namespace_provisioning.html',
        'operations.html',
    ):
        template = (ROOT / 'app/templates/kubernetes/tenant' / path).read_text(encoding='utf-8')
        assert 'workspace_tabs.html' not in template


def test_sidebar_authority_documents_tenant_capability_v21() -> None:
    standard = (ROOT / 'docs/design/components/SIDEBAR_NAVIGATION.md').read_text(encoding='utf-8')
    verifier = (ROOT / 'scripts/verify_sidebar_navigation_standard.py').read_text(encoding='utf-8')

    assert 'KAORI Sidebar Navigation Standard v2.2' in standard
    assert 'Level 1 — Workspace / Domain' in standard
    assert 'Level 2 — Capability' in standard
    assert 'Tenant' in standard
    assert "'tenant', 'Tenant', 'building-2', 'tenant.index'" in _navigation_source()
    assert 'two-level Workspace -> Capability sidebar' in verifier


def test_tenant_primary_navigation_preserves_provider_neutral_boundary() -> None:
    model = _navigation_source()
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    readme = (ROOT / 'app/kubernetes/tenant/README.md').read_text(encoding='utf-8')

    assert 'Native Kubernetes' in base
    assert 'Native Kubernetes' in readme
    assert 'Capsule' in readme
    assert 'Capsule' not in model


def test_tenant_registry_pages_use_shared_default_five_pagination() -> None:
    service = _tenant_service_source()
    tenant_registry = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_registry.html').read_text(
        encoding='utf-8'
    )

    assert '_ALLOWED_PAGE_SIZES = (5, 10, 25, 50)' in service
    for helper in (
        'get_tenant_registry_context',
        'get_resource_profile_registry_context',
        'get_namespace_registry_context',
    ):
        assert f'def {helper}(' in service

    assert 'tenant_pagination' in tenant_registry
    assert 'components/table_registry.html' in tenant_registry
    assert 'registry_ui.filter_form' in tenant_registry
    assert 'registry_ui.footer' in tenant_registry
    assert "'tenant.tenants'" in tenant_registry

    resource_profiles = (ROOT / 'app/templates/kubernetes/tenant/resource_profiles.html').read_text(encoding='utf-8')
    resource_profile_registry = (
        ROOT / 'app/templates/kubernetes/tenant/partials/_resource_profile_registry.html'
    ).read_text(encoding='utf-8')
    assert '_resource_profile_registry.html' in resource_profiles
    assert 'components/content_tabs.html' in resource_profiles
    assert 'content_tabs.render_links' in resource_profiles
    assert 'profile_pagination' in resource_profile_registry
    assert 'components/table_registry.html' in resource_profile_registry
    assert 'registry_ui.filter_form' in resource_profile_registry
    assert 'registry_ui.footer' in resource_profile_registry
    assert 'partials/_pagination_footer.html' not in resource_profile_registry

    namespace_page = (ROOT / 'app/templates/kubernetes/tenant/namespace_provisioning.html').read_text(encoding='utf-8')
    namespace_registry = (ROOT / 'app/templates/kubernetes/tenant/partials/_namespace_registry.html').read_text(
        encoding='utf-8'
    )
    assert '_namespace_registry.html' in namespace_page
    assert 'namespace_pagination' in namespace_registry
    assert 'components/table_registry.html' in namespace_registry
    assert 'registry_ui.filter_form' in namespace_registry
    assert 'registry_ui.footer' in namespace_registry
    assert 'namespace_search' in namespace_registry
    assert 'namespace_tenant_id' in namespace_registry
    assert 'namespace_environment' in namespace_registry
    assert 'namespace_status' in namespace_registry
    assert '_pagination_footer.html' not in namespace_page


def test_namespace_allocation_selector_is_not_limited_by_visible_page() -> None:
    service = _tenant_service_source()
    allocation = (ROOT / 'app/templates/kubernetes/tenant/partials/_allocation_change.html').read_text(encoding='utf-8')

    assert "'namespace_allocation_options': namespace_allocation_options" in service
    assert '{% for item in namespace_allocation_options %}' in allocation
    assert '{% for item in namespaces %}' not in allocation


def test_tenant_blocked_state_reuses_general_kubernetes_prerequisite_family() -> None:
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')

    blocked_index = base.index('{% if not native_available %}')
    onboarding_index = base.index('{% if registered_cluster_count == 0 %}')
    content_index = base.index('{% block tenant_content %}')

    assert 'components/cluster/_hero_blocked_context.html' in base
    assert 'components/cluster/_onboarding_banner.html' in base[onboarding_index:content_index]
    assert 'components/states/_blocked_state.html' not in base
    assert 'Tenant capability is blocked' not in base
    assert 'Return to Tenant' not in base
    assert "page_hero.context_card('Tenant context'" in base
    assert blocked_index < onboarding_index < content_index

    blocked_hero = base[blocked_index : base.index('{% else %}', blocked_index)]
    assert "page_hero.context_card('Tenant context'" not in blocked_hero
    assert 'Open Cluster Integrations' not in blocked_hero


def test_tenant_readiness_matches_runtime_fallback_and_blocker_distinguishes_validation() -> None:
    service = _tenant_service_source()
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    hero_blocker = (ROOT / 'app/templates/components/cluster/_hero_blocked_context.html').read_text(encoding='utf-8')
    onboarding = (ROOT / 'app/templates/components/cluster/_onboarding_banner.html').read_text(encoding='utf-8')

    native_provider = (ROOT / 'app/kubernetes/tenant/native_provider.py').read_text(encoding='utf-8')
    discovery = _tenant_discovery_source()

    assert 'tenant_workspace_connection_available' in service
    assert "frozenset({'ready', 'degraded'})" in native_provider
    assert 'def effective_native_connection_readiness(' in native_provider
    assert "== 'connected' else 'validation_required'" in native_provider
    assert 'effective_native_connection_readiness(connection)' in native_provider
    assert 'tenant_workspace_connection_available(cluster.kubernetes_connection)' in discovery
    assert 'Metrics Source' not in service
    assert 'Alertmanager' not in service

    assert 'registered_cluster_count = cluster_onboarding.cluster_count|default(0)' in base
    assert 'Provider Operations Restricted' in base
    assert 'Registered Clusters' in base
    assert 'Provider mutations require a Ready Kubernetes integration.' in base

    assert 'blocked_cluster_value' in hero_blocker
    assert 'blocked_cluster_supporting' in hero_blocker
    assert 'Validate Your Kubernetes Cluster' in onboarding
    assert (
        'Cluster registered, but this workspace needs a Ready integration or pending legacy readiness persistence.'
        in onboarding
    )
    assert 'Open Cluster Integrations' in onboarding
    assert 'Validate Cluster' in onboarding
    assert 'Confirm Ready' in onboarding


def test_tenant_detail_uses_tenants_active_capability_and_contextual_topbar():
    source = _read('app/common/workspace_navigation.py')
    breadcrumb = _read('app/common/navigation.py')
    sidebar = _read('app/templates/components/navigation/tenant_menu.html')
    page = _read('app/templates/kubernetes/tenant/tenant_detail.html')
    partial = _read('app/templates/kubernetes/tenant/partials/_tenant_management_detail.html')
    assert "'tenant.tenant_detail': 'tenants'" in source
    assert "'tenant.tenant_detail': 'Tenant Details'" in breadcrumb
    assert "elif endpoint == 'tenant.tenant_detail':" in breadcrumb
    assert "'tenant.tenant_detail'" in sidebar
    assert '{% block dashboard_content %}' in page
    assert '{% block tenant_content %}' not in page
    assert 'data-kaori-hero-profile="transactional-admin"' in partial
    assert partial.count('Back to Registry') == 1


def test_tenant_detail_runtime_navigation_projection_is_tenants_not_overview():
    from app.common.navigation import build_navigation_breadcrumb
    from app.common.workspace_navigation import _capability_active_key

    assert _capability_active_key('kubernetes_tenant', 'tenant.tenant_detail') == 'tenants'
    assert [item['label'] for item in build_navigation_breadcrumb('tenant.tenant_detail')] == [
        'Kubernetes', 'Tenant', 'Tenants', 'Tenant Details',
    ]
