from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_uat_surface_uses_one_kubernetes_sidebar_destination() -> None:
    sidebar = (ROOT / 'app/templates/components/navigation/sidebar.html').read_text(encoding='utf-8')
    tenant_menu = (ROOT / 'app/templates/components/navigation/tenant_menu.html').read_text(encoding='utf-8')
    template = (ROOT / 'app/templates/kubernetes/tenant/index.html').read_text(encoding='utf-8')
    navigation = (ROOT / 'app/common/navigation.py').read_text(encoding='utf-8')
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')

    assert "has_permission('tenant.view')" in sidebar
    assert "has_permission('tenant.manage')" in sidebar
    assert sidebar.count('components/navigation/tenant_menu.html') == 1
    assert '>Tenant</span>' in tenant_menu
    assert "url_for('tenant.index')" in tenant_menu
    assert "page_hero.intro('building-2', 'Kubernetes', 'building-2')" in template
    assert 'Native Kubernetes only.' in template
    assert 'Capsule remains unavailable until the Capsule provider discovery' in template
    assert "'tenant': ('Tenant', 'building-2', 'Overview')" in navigation


def test_tenant_uat_surface_separates_platform_permission_from_tenant_membership() -> None:
    registry = (ROOT / 'app/definitions/catalogs/access/rbac/access.yaml').read_text(encoding='utf-8')
    rbac_doc = (ROOT / 'docs/rbac/README.md').read_text(encoding='utf-8')

    assert '- key: tenant.view' in registry
    assert '- key: tenant.manage' in registry
    assert 'tenant.manage: [tenant.view]' in registry
    assert 'do not represent membership inside a managed tenant' in rbac_doc
