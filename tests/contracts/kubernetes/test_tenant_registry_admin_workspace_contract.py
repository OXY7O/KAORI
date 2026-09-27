from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tenants_page_keeps_summary_above_the_tabbed_workspace() -> None:
    page = read('app/templates/kubernetes/tenant/tenants.html')
    admin = read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    routes = read('app/kubernetes/tenant/routes.py')

    assert "'Tenant Summary'" in page
    assert "'Governance Estate'" in page
    assert 'tenant_summary_metrics' in page
    assert page.index("'Tenant Summary'") < page.index("'Tenant Workspace'")
    assert page.index("'Tenant Workspace'") < page.index('partials/_tenant_admin_workspace.html')

    assert 'components/content_tabs.html' in admin
    assert 'content_tabs.render_links' in admin
    assert "('registry', 'Tenant Registry'" in admin
    assert "('tenant-setup', 'Tenant Setup'" in admin
    assert "('memberships', 'Memberships'" in admin
    assert "('access-grants', 'Access Grants'" in admin
    assert "('credentials', 'Credentials'" in admin
    assert "('namespace-access', 'Namespace Access'" in admin
    assert "hx_target='#tenant-admin-workspace'" in admin
    assert "hx_select='#tenant-admin-workspace'" in admin
    assert "hx_push_url='true'" in admin
    assert "hx_sync='this:replace'" in admin

    assert "'registry'," in routes
    assert "normalized = str(value or 'registry')" in routes


def test_tenant_registry_uses_canonical_server_registry_contract() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')
    service = read('app/kubernetes/tenant/service.py')

    assert 'components/table.html' in registry
    assert 'components/table_registry.html' in registry
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.footer' in registry
    assert 'tenant-registry-loading' in registry
    assert "table_ui.table_classes('min-w-[980px]')" in registry
    assert 'tenant-registry-cluster' in registry
    assert 'tenant-registry-environment' in registry
    assert 'tenant-registry-lifecycle' in registry
    assert 'tenant-registry-search' in registry
    assert "resource_label='Tenants'" in registry
    assert "'tenant.tenants'" in registry
    assert 'No Tenants Found' in registry

    assert 'def get_tenant_registry_context(' in service
    assert 'search: str' in service
    assert 'cluster_id: str' in service
    assert 'environment: str' in service
    assert 'lifecycle_status: str' in service
    assert 'func.lower(Tenant.name).like(pattern)' in service
    assert 'func.lower(Tenant.slug).like(pattern)' in service
    assert 'TenantEnvironment.environment == normalized_environment' in service


def test_tenant_setup_uses_a_static_governance_flow_not_expandable_guidance() -> None:
    setup = read('app/templates/kubernetes/tenant/partials/_tenant_setup_workspace.html')

    assert 'components/operational_flow_steps.html' in setup
    assert 'Tenant Governance Flow' in setup
    for label in ('Create Tenant', 'Provision Namespace', 'Add Membership', 'Apply Access Grant', 'Issue Credential'):
        assert label in setup
    assert 'Important Boundaries' in setup
    assert 'context_guidance_card.html' not in setup
    assert 'open_by_default' not in setup


def test_memberships_use_symmetric_actions_and_scalable_registries() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    memberships = read('app/templates/kubernetes/tenant/partials/_membership_registry.html')
    groups = read('app/templates/kubernetes/tenant/partials/_group_registry.html')
    read_model = read('app/kubernetes/tenant/admin_workspace.py')

    assert 'Membership Model' in workspace
    assert 'components/operational_flow_steps.html' in workspace
    assert 'xl:grid-cols-3' in workspace
    for label in ('Add User Membership', 'Create Tenant Group', 'Add Group Membership'):
        assert label in workspace
    assert '_membership_registry.html' in workspace
    assert '_group_registry.html' in workspace

    for table in (memberships, groups):
        assert 'components/table.html' in table
        assert 'components/table_registry.html' in table
        assert 'registry_ui.filter_form' in table
        assert 'registry_ui.footer' in table

    assert 'def get_membership_registry_context(' in read_model
    assert 'def get_group_registry_context(' in read_model
    assert 'paginate_query(' in read_model


def test_access_grants_use_wide_form_and_full_registry() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    read_model = read('app/kubernetes/tenant/admin_workspace.py')

    assert 'Access Grant Model' in workspace
    assert 'id="access-grant-form"' in workspace
    assert 'md:grid-cols-2 xl:grid-cols-3' in workspace
    assert '_access_grant_registry.html' in workspace
    assert "'Access Grant Registry'" in registry
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.footer' in registry
    assert 'Inspect' in registry
    assert 'Reconcile' in registry
    assert 'Revoke' in registry
    assert 'def get_access_grant_registry_context(' in read_model


def test_credentials_use_symmetric_issuance_and_full_lifecycle_table() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_credentials_workspace.html')
    registry = read('app/templates/kubernetes/tenant/partials/_credential_registry.html')
    read_model = read('app/kubernetes/tenant/admin_workspace.py')

    assert 'xl:grid-cols-2 xl:items-stretch' in workspace
    assert workspace.count('flex h-full flex-col') >= 2
    assert 'Issue Human Access' in workspace
    assert 'Issue CI/CD Deployer' in workspace
    assert workspace.count('Delivery Contract') == 2
    assert '_credential_registry.html' in workspace

    assert "'Credential Lifecycle'" in registry
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.footer' in registry
    for action in ('Renew', 'Suspend', 'Resume', 'Revoke'):
        assert action in registry
    assert 'def get_credential_registry_context(' in read_model


def test_namespace_access_is_a_paginated_non_secret_registry() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html')
    registry = read('app/templates/kubernetes/tenant/partials/_namespace_access_registry.html')
    read_model = read('app/kubernetes/tenant/admin_workspace.py')

    assert 'Effective Namespace Access' in workspace
    assert 'Security Boundary' in workspace
    assert '_namespace_access_registry.html' in workspace
    assert "'Namespace Access Registry'" in registry
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.footer' in registry
    assert 'approved_access_methods' in registry
    assert 'credential.token' not in registry
    assert 'credential.kubeconfig' not in registry
    assert 'private_key' not in registry
    assert 'def get_namespace_access_registry_context(' in read_model
    assert 'paginate_sequence(' in read_model


def test_tenant_administration_retires_monolithic_uat_partials() -> None:
    assert not (ROOT / 'app/templates/kubernetes/tenant/partials/_members_access.html').exists()
    assert not (ROOT / 'app/templates/kubernetes/tenant/partials/_credential_management.html').exists()

    for path in (
        'app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html',
        'app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html',
        'app/templates/kubernetes/tenant/partials/_tenant_credentials_workspace.html',
        'app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html',
    ):
        assert 'Functional UAT Surface' not in read(path)


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
