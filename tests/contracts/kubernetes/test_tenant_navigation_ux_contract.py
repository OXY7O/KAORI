import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_uses_canonical_expandable_sidebar_parent() -> None:
    menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')

    assert '<details class="sidebar-menu space-y-1"' in menu
    assert 'sidebar-menu-chevron' in menu
    assert 'sidebar-submenu' in menu

    for endpoint, label in (
        ('tenant.index', 'Overview'),
        ('tenant.tenants', 'Tenants'),
        ('tenant.resource_profiles', 'Resource Profiles'),
        ('tenant.namespace_provisioning', 'Namespace Provisioning'),
        ('tenant.operations', 'Operations'),
    ):
        assert f"url_for('{endpoint}')" in menu
        assert f'>{label}</span>' in menu


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

    for label in ('Provisioning', 'Runs & Evidence', 'Drift & Reconcile', 'Activity'):
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


def test_sidebar_authority_documents_tenant_submenu_v17() -> None:
    standard = (ROOT / 'docs/design/components/SIDEBAR_NAVIGATION.md').read_text(encoding='utf-8')
    verifier = (ROOT / 'scripts/verify_sidebar_navigation_standard.py').read_text(encoding='utf-8')

    assert 'KAORI Sidebar Navigation Standard v1.7' in standard
    assert 'Tenant remains one Kubernetes capability parent' in standard
    for label in ('Overview', 'Tenants', 'Resource Profiles', 'Namespace Provisioning', 'Operations'):
        assert label in standard
        assert label in verifier


def test_tenant_primary_navigation_preserves_provider_neutral_boundary() -> None:
    menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    readme = (ROOT / 'app/kubernetes/tenant/README.md').read_text(encoding='utf-8')

    assert 'Native Kubernetes' in base
    assert 'Native Kubernetes' in readme
    assert 'Capsule' in readme
    assert 'Native Kubernetes</span>' not in menu
    assert 'Capsule</span>' not in menu


def test_tenant_registry_pages_use_shared_default_five_pagination() -> None:
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')
    footer = (ROOT / 'app/templates/kubernetes/tenant/partials/_pagination_footer.html').read_text(encoding='utf-8')
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

    assert 'components/pagination.html' in footer
    assert 'pagination_ui.numeric_pages' in footer
    assert 'pagination_ui.page_size_classes' in footer

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
    assert 'profile_pagination' in resource_profile_registry
    assert 'partials/_pagination_footer.html' in resource_profile_registry

    namespace_template = (
        ROOT / 'app/templates/kubernetes/tenant/namespace_provisioning.html'
    ).read_text(encoding='utf-8')
    assert 'namespace_pagination' in namespace_template
    assert 'partials/_pagination_footer.html' in namespace_template


def test_namespace_allocation_selector_is_not_limited_by_visible_page() -> None:
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')
    allocation = (ROOT / 'app/templates/kubernetes/tenant/partials/_allocation_change.html').read_text(encoding='utf-8')

    assert "'namespace_options': namespace_options" in service
    assert '{% for item in namespace_options %}' in allocation
    assert '{% for item in namespaces %}' not in allocation
