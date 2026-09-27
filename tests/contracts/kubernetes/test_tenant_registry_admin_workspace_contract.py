from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tenant_registry_uses_canonical_kaori_table_family() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')
    service = read('app/kubernetes/tenant/service.py')
    routes = read('app/kubernetes/tenant/routes.py')

    assert 'components/table.html' in registry
    assert 'components/pagination.html' in registry
    assert 'components/table_registry.html' in registry
    assert "'Tenant Registry'" in registry
    assert 'tenant-registry-loading' in registry
    assert 'table_ui.inventory_filter_bar_classes()' in registry
    assert 'tenant-registry-cluster' in registry
    assert 'tenant-registry-environment' in registry
    assert 'tenant-registry-lifecycle' in registry
    assert 'tenant-registry-search' in registry
    assert "table_ui.table_classes('min-w-[980px]')" in registry
    assert 'pagination_ui.page_size_classes()' in registry
    assert 'pagination_ui.numeric_pages(' in registry
    assert "endpoint='tenant.tenant_registry'" in registry
    assert "href_endpoint='tenant.tenants'" in registry
    assert 'tenant_pagination.allowed_per_page' in registry
    assert 'No Tenants Found' in registry

    assert 'def get_tenant_registry_context(' in service
    assert 'search: str' in service
    assert 'cluster_id: str' in service
    assert 'environment: str' in service
    assert 'lifecycle_status: str' in service
    assert 'func.lower(Tenant.name).like(pattern)' in service
    assert 'func.lower(Tenant.slug).like(pattern)' in service
    assert 'TenantEnvironment.environment == normalized_environment' in service
    assert "'tenant_rows': tenant_rows" in service
    assert "'tenant_registry_filters':" in service

    assert "@tenant_bp.get('/tenants/registry')" in routes
    assert "def tenant_registry():" in routes


def test_tenant_page_keeps_registry_primary_and_administration_subordinate() -> None:
    page = read('app/templates/kubernetes/tenant/tenants.html')
    admin = read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')

    assert page.index("'Tenant Estate'") < page.index('partials/_tenant_registry.html')
    assert page.index('partials/_tenant_registry.html') < page.index("'Administration Workspace'")
    assert page.index("'Administration Workspace'") < page.index('partials/_tenant_admin_workspace.html')

    assert 'components/content_tabs.html' in admin
    assert 'content_tabs.render_links' in admin
    assert "hx_target='#tenant-admin-workspace'" in admin
    assert "hx_select='#tenant-admin-workspace'" in admin
    assert "hx_push_url='true'" in admin
    assert "hx_indicator='#tenant-admin-loading'" in admin
    assert "hx_sync='this:replace'" in admin

    for key, label, partial in (
        ('tenant-setup', 'Tenant Setup', '_tenant_setup_workspace.html'),
        ('memberships', 'Memberships', '_tenant_memberships_workspace.html'),
        ('access-grants', 'Access Grants', '_tenant_access_grants_workspace.html'),
        ('credentials', 'Credentials', '_tenant_credentials_workspace.html'),
        ('namespace-access', 'Namespace Access', '_tenant_namespace_access_workspace.html'),
    ):
        assert key in admin
        assert label in admin
        assert partial in admin


def test_tenant_administration_retires_monolithic_uat_partials() -> None:
    assert not (ROOT / 'app/templates/kubernetes/tenant/partials/_members_access.html').exists()
    assert not (ROOT / 'app/templates/kubernetes/tenant/partials/_credential_management.html').exists()

    memberships = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    grants = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    credentials = read('app/templates/kubernetes/tenant/partials/_tenant_credentials_workspace.html')
    namespace_access = read('app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html')

    assert 'Functional UAT Surface' not in memberships
    assert 'Add User Membership' in memberships
    assert 'Tenant Group' in memberships
    assert 'Apply Access Grant' in grants
    assert 'Issue Human Access' in credentials
    assert 'Issue CI/CD Deployer' in credentials
    assert 'Credential Lifecycle' in credentials
    assert 'Namespace Access' in namespace_access


def test_tenant_mutations_return_to_the_relevant_administration_section() -> None:
    routes = read('app/kubernetes/tenant/routes.py')

    assert "_tenant_section_redirect('tenant-setup')" in routes
    assert routes.count("_tenant_section_redirect('memberships')") >= 4
    assert routes.count("_tenant_section_redirect('access-grants')") >= 4
    assert routes.count("_tenant_section_redirect('credentials')") >= 6
    assert "return redirect(url_for('tenant.tenants'))" not in routes


def test_overview_attention_and_activity_rows_share_peer_geometry() -> None:
    overview = read('app/templates/kubernetes/tenant/overview.html')

    assert overview.count('min-h-[7.5rem]') >= 3
    assert 'Committed governance finding' in overview
    assert 'Recent Tenant Activity' in overview
    assert 'Needs Attention' in overview
