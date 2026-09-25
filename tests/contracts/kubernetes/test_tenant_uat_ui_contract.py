from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_workspace_uses_one_expandable_kubernetes_sidebar_destination() -> None:
    sidebar = (ROOT / 'app/templates/components/navigation/sidebar.html').read_text(encoding='utf-8')
    tenant_menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')
    overview = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text(encoding='utf-8')
    resource_profiles = (ROOT / 'app/templates/kubernetes/tenant/resource_profiles.html').read_text(encoding='utf-8')
    operations = (ROOT / 'app/templates/kubernetes/tenant/operations.html').read_text(encoding='utf-8')
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
        assert f"url_for('{endpoint}')" in tenant_menu

    assert 'Tenant Management, Resource Profiles & Namespace Operations' in overview
    assert 'Native Kubernetes Active' in (ROOT / 'app/templates/kubernetes/tenant/_hero.html').read_text(
        encoding='utf-8'
    )
    assert 'Capsule Planned' in (ROOT / 'app/templates/kubernetes/tenant/_hero.html').read_text(encoding='utf-8')
    assert 'Preset classes auto-fill canonical values' in resource_profiles
    assert "('provisioning', 'Provisioning'" in operations
    assert "('runs', 'Runs & Evidence'" in operations
    assert "('drift', 'Drift & Reconcile'" in operations
    assert "('activity', 'Activity'" in operations
    assert "'tenant.resource_profiles': 'Resource Profiles'" in navigation
    assert routes.count("@any_permission_required('tenant.view', 'tenant.manage')") == 5
    assert routes.count("@permission_required('tenant.manage')") == 3


def test_tenant_workspace_keeps_native_actionable_and_capsule_non_actionable() -> None:
    tenants = (ROOT / 'app/templates/kubernetes/tenant/tenants.html').read_text(encoding='utf-8')
    namespace = (ROOT / 'app/templates/kubernetes/tenant/namespace_provisioning.html').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')

    assert 'Native Kubernetes' in tenants
    assert 'Capsule' in tenants
    assert 'Provider selection remains blocked' in tenants
    assert 'Native Kubernetes is actionable' in namespace
    assert "tenant.provider_key = 'native_kubernetes'" in service
    assert "'capsule'" not in service.split('RESOURCE_PROFILE_PRESETS', 1)[0]


def test_resource_profile_presets_are_server_authoritative() -> None:
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')
    script = (ROOT / 'app/static/js/kubernetes/tenant_resource_profiles.js').read_text(encoding='utf-8')

    assert 'RESOURCE_PROFILE_PRESETS' in service
    assert "if profile_class == TenantResourceProfileClass.CUSTOM.value" in service
    assert "preset = RESOURCE_PROFILE_PRESETS[profile_class]" in service
    assert "input.readOnly = !custom" in script
    assert "if (custom)" in script


def test_tenant_uat_surface_separates_platform_permission_from_tenant_membership() -> None:
    registry = (ROOT / 'app/definitions/catalogs/access/rbac/access.yaml').read_text(encoding='utf-8')
    rbac_doc = (ROOT / 'docs/rbac/README.md').read_text(encoding='utf-8')

    assert '- key: tenant.view' in registry
    assert '- key: tenant.manage' in registry
    assert 'tenant.manage: [tenant.view]' in registry
    assert 'do not represent membership inside a managed tenant' in rbac_doc
