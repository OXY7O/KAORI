from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tenant_uat_surface_uses_one_expandable_parent_with_five_submenu_destinations() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    catalog = _read('app/common/workspace_navigation_catalog.py')
    navigation_model = _read('app/common/workspace_navigation.py')
    tenant_menu = _read('app/templates/components/navigation/tenant_menu.html')
    navigation = _read('app/common/navigation.py')
    routes = _read('app/kubernetes/tenant/routes.py')

    assert "('tenant.view', 'tenant.manage')" in catalog
    assert "'tenant', 'Tenant', 'building-2', 'tenant.index'" in catalog
    assert '_visible_capabilities(workspace, user)' in navigation_model
    assert 'data-kaori-sidebar-capability="{{ child[\'key\'] }}"' in sidebar
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
    namespace_registry = _read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')
    operations = _read('app/templates/kubernetes/tenant/operations.html')

    assert "'Multi-Cluster Posture'" in tenants
    assert "'Tenant Estate'" in tenants
    assert 'partials/_tenant_admin_workspace.html' in tenants
    admin = _read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    assert 'components/content_tabs.html' in admin
    assert 'content_tabs.render_links' in admin
    for partial in (
        '_tenant_registry.html',
        '_tenant_setup_workspace.html',
        '_tenant_memberships_workspace.html',
        '_tenant_access_grants_workspace.html',
        '_tenant_credentials_workspace.html',
        '_tenant_namespace_access_workspace.html',
    ):
        assert partial in admin

    assert 'partials/_resource_profile_form.html' in profiles
    assert 'partials/_capacity_governance.html' in profiles

    assert 'Namespace Provisioning Snapshot' in namespaces
    assert 'Namespace Estate' in namespaces
    assert 'Namespace Provisioning Workspace' in namespaces
    assert 'Namespace Administration' in namespaces
    assert 'content_tabs.render_links' in namespaces
    assert 'active_namespace_view' in namespaces
    assert 'partials/_namespace_form.html' in namespaces
    assert 'partials/_namespace_registry.html' in namespaces
    assert 'partials/_allocation_change.html' in namespaces
    assert 'partials/_capacity_decisions.html' in namespaces
    assert 'id="tenant-namespace-allocation-profiles"' in namespaces
    assert 'id="tenant-namespace-allocation-state"' in namespaces
    assert 'components/table_registry.html' in namespace_registry
    assert 'registry_ui.filter_form' in namespace_registry
    assert 'registry_ui.footer' in namespace_registry

    assert 'Tenant Operations Snapshot' in operations
    assert 'Operations Estate' in operations
    assert 'Tenant Operations Workspace' in operations
    assert 'Operational Control' in operations
    assert 'content_tabs.render_links' in operations
    assert "hx_target='#tenant-operations-workspace'" in operations
    for partial in (
        '_operations_namespace_registry.html',
        '_operations_evidence_registry.html',
        '_operations_drift_registry.html',
        '_operations_provider_registry.html',
        '_operations_access_reconciliation_registry.html',
    ):
        assert partial in operations


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


def test_tenant_operations_data_surfaces_are_canonical_paginated_registries() -> None:
    routes = _read('app/kubernetes/tenant/routes.py')
    route_common = _read('app/kubernetes/tenant/route_common.py')
    workspace = _read('app/kubernetes/tenant/workspace.py')
    partial_paths = (
        'app/templates/kubernetes/tenant/partials/_operations_namespace_registry.html',
        'app/templates/kubernetes/tenant/partials/_operations_evidence_registry.html',
        'app/templates/kubernetes/tenant/partials/_operations_drift_registry.html',
        'app/templates/kubernetes/tenant/partials/_operations_provider_registry.html',
        'app/templates/kubernetes/tenant/partials/_operations_access_reconciliation_registry.html',
    )

    for partial_path in partial_paths:
        partial = _read(partial_path)
        assert 'components/table.html' in partial
        assert 'components/table_registry.html' in partial
        assert 'registry_ui.filter_form' in partial
        assert 'registry_ui.footer' in partial

    for key in (
        'ops_namespace_per_page',
        'ops_evidence_per_page',
        'ops_drift_per_page',
        'ops_provider_per_page',
        'ops_access_per_page',
    ):
        assert key in routes or key in route_common
    assert 'get_tenant_operations_evidence_context' in routes
    assert '_OPERATIONS_EVIDENCE_TYPES' in workspace
    assert 'paginate_query(' in workspace
