from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tenant_uat_surface_uses_one_expandable_parent_with_five_submenu_destinations() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    tenant_menu = _read('app/templates/components/navigation/tenant_menu.html')
    navigation = _read('app/common/navigation.py')
    routes = _read('app/kubernetes/tenant/routes.py')

    assert "has_permission('tenant.view')" in sidebar
    assert "has_permission('tenant.manage')" in sidebar
    assert sidebar.count('components/navigation/tenant_menu.html') == 1
    assert '<details class="sidebar-menu space-y-1"' in tenant_menu

    for endpoint, label in (
        ('tenant.index', 'Overview'),
        ('tenant.tenants', 'Tenants'),
        ('tenant.resource_profiles', 'Resource Profiles'),
        ('tenant.namespace_provisioning', 'Namespace Provisioning'),
        ('tenant.operations', 'Operations'),
    ):
        assert f"url_for('{endpoint}')" in tenant_menu
        assert f"'{endpoint}': '{label}'" in navigation

    for mutation in (
        '/tenants',
        '/resource-profiles',
        '/capacity-policy',
        '/namespaces',
        '/namespace-allocation',
    ):
        assert f"@tenant_bp.post('{mutation}')\n@permission_required('tenant.manage')" in routes


def test_tenant_uat_pages_preserve_current_admitted_workflows() -> None:
    tenants = _read('app/templates/kubernetes/tenant/tenants.html')
    profiles = _read('app/templates/kubernetes/tenant/resource_profiles.html')
    namespaces = _read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    operations = _read('app/templates/kubernetes/tenant/operations.html')

    assert 'partials/_tenant_registry.html' in tenants
    assert 'partials/_tenant_admin_workspace.html' in tenants
    admin = _read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    assert 'components/content_tabs.html' in admin
    assert 'content_tabs.render_links' in admin
    for partial in (
        '_tenant_setup_workspace.html',
        '_tenant_memberships_workspace.html',
        '_tenant_access_grants_workspace.html',
        '_tenant_credentials_workspace.html',
        '_tenant_namespace_access_workspace.html',
    ):
        assert partial in admin

    assert 'partials/_resource_profile_form.html' in profiles
    assert 'partials/_capacity_governance.html' in profiles

    assert 'partials/_namespace_form.html' in namespaces
    assert 'partials/_allocation_change.html' in namespaces
    assert 'partials/_capacity_decisions.html' in namespaces
    assert 'id="tenant-namespace-allocation-profiles"' in namespaces
    assert 'id="tenant-namespace-allocation-state"' in namespaces

    assert 'content_tabs.render_links' in operations
    assert 'Kubernetes Audit Evidence' in operations
    assert 'Managed Resources &amp; Policies' in operations


def test_tenant_uat_surface_separates_platform_permission_from_tenant_membership() -> None:
    registry = _read('app/definitions/catalogs/access/rbac/access.yaml')
    rbac_doc = _read('docs/rbac/README.md')

    assert '- key: tenant.view' in registry
    assert '- key: tenant.manage' in registry
    assert 'tenant.manage: [tenant.view]' in registry
    assert 'do not represent membership inside a managed tenant' in rbac_doc


def test_tenant_provider_scope_remains_provider_neutral_in_navigation() -> None:
    menu = _read('app/templates/components/navigation/tenant_menu.html')
    base = _read('app/templates/kubernetes/tenant/base.html')

    assert 'Native Kubernetes' in base
    assert 'Provider Readiness' in base
    assert 'Native Kubernetes</span>' not in menu
    assert 'Capsule</span>' not in menu
