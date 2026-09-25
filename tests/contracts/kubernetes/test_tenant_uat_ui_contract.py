from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_workspace_uses_one_parent_with_capability_submenu() -> None:
    sidebar = (ROOT / 'app/templates/components/navigation/sidebar.html').read_text(encoding='utf-8')
    tenant_menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')
    navigation = (ROOT / 'app/common/navigation.py').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

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
        assert f'>{label}</span>' in tenant_menu
    assert "'tenant': ('Tenant', 'building-2', 'Overview')" in navigation
    assert routes.count("@permission_required('tenant.manage')") == 3


def test_tenant_provider_scope_stays_native_until_capsule_qualification() -> None:
    base = (ROOT / 'app/templates/kubernetes/tenant/base.html').read_text(encoding='utf-8')
    namespaces = (ROOT / 'app/templates/kubernetes/tenant/namespace_provisioning.html').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')

    assert 'Native Kubernetes · Active' in base
    assert 'Capsule · Planned / Not yet qualified' in base
    assert 'Native Kubernetes only.' in namespaces
    assert "tenant.provider_key != 'native_kubernetes'" in service


def test_resource_profile_presets_are_server_authoritative_and_custom_is_manual() -> None:
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/resource_profiles.html').read_text(encoding='utf-8')
    javascript = (ROOT / 'app/static/js/tenant_resource_profiles.js').read_text(encoding='utf-8')

    assert 'RESOURCE_PROFILE_PRESETS' in service
    assert "if profile_class in RESOURCE_PROFILE_PRESETS" in service
    assert "profile_class == TenantResourceProfileClass.CUSTOM.value" in service
    assert 'Preset classes are auto-filled and server-authoritative.' in template
    assert 'data-tenant-profile-class' in template
    assert "profileClass === 'custom'" in javascript


def test_tenant_uat_surface_separates_platform_permission_from_tenant_membership() -> None:
    registry = (ROOT / 'app/definitions/catalogs/access/rbac/access.yaml').read_text(encoding='utf-8')
    rbac_doc = (ROOT / 'docs/rbac/README.md').read_text(encoding='utf-8')

    assert '- key: tenant.view' in registry
    assert '- key: tenant.manage' in registry
    assert 'tenant.manage: [tenant.view]' in registry
    assert 'do not represent membership inside a managed tenant' in rbac_doc
