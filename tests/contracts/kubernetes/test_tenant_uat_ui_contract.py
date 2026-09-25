from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_workspace_uses_one_expandable_kubernetes_parent() -> None:
    sidebar = (ROOT / 'app/templates/components/navigation/sidebar.html').read_text(encoding='utf-8')
    tenant_menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')
    navigation = (ROOT / 'app/common/navigation.py').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    assert "has_permission('tenant.view')" in sidebar
    assert "has_permission('tenant.manage')" in sidebar
    assert sidebar.count('components/navigation/tenant_menu.html') == 1
    assert '<details class="sidebar-menu space-y-1"' in tenant_menu
    for endpoint in (
        'tenant.index',
        'tenant.tenants',
        'tenant.resource_profiles',
        'tenant.namespace_provisioning',
        'tenant.operations',
    ):
        assert f"'{endpoint}'" in tenant_menu
        assert f"'{endpoint}':" in navigation
    assert "@any_permission_required('tenant.view', 'tenant.manage')" in routes
    assert routes.count("@permission_required('tenant.manage')") == 3


def test_tenant_native_baseline_is_explicit_and_capsule_is_not_actionable() -> None:
    overview = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')
    tenants = (ROOT / 'app/templates/kubernetes/tenant/tenants.html').read_text(encoding='utf-8')
    namespace = (ROOT / 'app/templates/kubernetes/tenant/namespace_provisioning.html').read_text(encoding='utf-8')
    hero = (ROOT / 'app/templates/kubernetes/tenant/partials/_hero.html').read_text(encoding='utf-8')

    assert 'Tenant Management, Resource Profiles & Namespace Operations' in overview
    assert 'Native Kubernetes is the only actionable provider' in tenants
    assert 'Native Kubernetes only.' in namespace
    assert 'Capsule' in hero
    assert 'Not yet qualified' in hero


def test_resource_profile_ui_uses_canonical_presets_and_custom_manual_mode() -> None:
    template = (ROOT / 'app/templates/kubernetes/tenant/resource_profiles.html').read_text(encoding='utf-8')
    javascript = (ROOT / 'app/static/js/tenant_resource_profiles.js').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')

    assert "('small', 'Small'" in template
    assert "('standard', 'Standard'" in template
    assert "('large', 'Large'" in template
    assert "('custom', 'Custom'" in template
    assert 'data-profile-field' in template
    assert "profileClass === 'custom'" in javascript
    assert 'resolve_profile_values(profile_class, source)' in service


def test_tenant_operations_stays_one_submenu_with_internal_tabs() -> None:
    menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')
    operations = (ROOT / 'app/templates/kubernetes/tenant/operations.html').read_text(encoding='utf-8')

    assert menu.count("'tenant.operations'") == 1
    for label in ('Provisioning', 'Runs & Evidence', 'Drift & Reconcile', 'Activity'):
        assert label in operations


def test_tenant_uat_surface_separates_platform_permission_from_tenant_membership() -> None:
    registry = (ROOT / 'app/definitions/catalogs/access/rbac/access.yaml').read_text(encoding='utf-8')
    rbac_doc = (ROOT / 'docs/rbac/README.md').read_text(encoding='utf-8')

    assert '- key: tenant.view' in registry
    assert '- key: tenant.manage' in registry
    assert 'tenant.manage: [tenant.view]' in registry
    assert 'do not represent membership inside a managed tenant' in rbac_doc
