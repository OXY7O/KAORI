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


def test_tenant_group_edit_modal_uses_canonical_primary_and_secondary_actions() -> None:
    group = _read('app/templates/kubernetes/tenant/partials/_group_registry.html')
    action = _read('app/templates/components/action_button.html')
    assert '{% import "components/action_button.html" as action_button %}' in group
    footer = group.split('<footer class="flex flex-col-reverse gap-2', 1)[1].split('</footer>', 1)[0]
    assert 'data-tenant-group-edit-close' in footer
    assert 'class="{{ action_button.classes(\'secondary\') }}"' in footer
    assert 'type="submit"' in footer
    assert 'class="{{ action_button.classes(\'primary\') }}"' in footer
    assert 'Save Changes' in footer
    assert "variant == 'primary'" in action
    assert 'disabled:bg-status-disabled-soft' in action
    assert 'hx-disabled-elt="find button"' in group
    assert 'data-tenant-group-edit-subject' in group


def test_namespace_allocation_workflow_uses_distinct_primary_provider_tabs() -> None:
    """#2998: three workflows replace the overlong stacked Allocation Change tab."""
    from jinja2 import Environment

    workspace = _read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    tabs = _read('app/templates/components/content_tabs.html')
    routes = _read('app/kubernetes/tenant/routes.py')

    Environment(autoescape=True).parse(workspace)
    assert "content_tabs.render_links('namespace-provisioning'," in workspace
    assert "data_namespace='namespace-provisioning'" in workspace
    assert "hx_target='#namespace-provisioning-workspace'" in workspace
    assert "hx_select='#namespace-provisioning-workspace'" in workspace
    assert "hx_push_url='true'" in workspace
    assert 'nowrap=true' in workspace
    assert 'overflow-x-auto' in tabs

    tab_labels = (
        ('provision', 'Provision Namespace'),
        ('allocation', 'Native Allocation'),
        ('native-cutover', 'Native Cutover'),
        ('capsule-governance', 'Capsule Governance'),
        ('decisions', 'Capacity Decisions'),
    )
    for key, label in tab_labels:
        assert f"('{key}', '{label}', " in workspace
        assert f"view='{key}'" in workspace
    # Five primary links plus three Capsule authority subview links.
    assert workspace.count("url_for('tenant.namespace_provisioning', view=") == 8
    assert "('allocation', 'Allocation Change'" not in workspace

    native = workspace.split("{% if active_namespace_view == 'allocation' %}", 1)[1].split(
        "{% elif active_namespace_view == 'native-cutover' %}", 1
    )[0]
    cutover = workspace.split("{% elif active_namespace_view == 'native-cutover' %}", 1)[1].split(
        "{% elif active_namespace_view == 'capsule-governance' %}", 1
    )[0]
    capsule = workspace.split("{% elif active_namespace_view == 'capsule-governance' %}", 1)[1].split(
        "{% elif active_namespace_view == 'decisions' %}", 1
    )[0]
    assert native.count('_allocation_change.html') == 1
    assert '_allocation_cutover.html' not in native and '_capsule_' not in native
    assert cutover.count('_allocation_cutover.html') == 1
    assert '_allocation_change.html' not in cutover and '_capsule_' not in cutover
    assert capsule.count('_capsule_tenant_quota_cutover.html') == 1
    assert capsule.count('_capsule_shared_allocation_cutover.html') == 1
    assert '_allocation_change.html' not in capsule and '_allocation_cutover.html' not in capsule
    assert '<details' not in native and '<details' not in cutover and '<details' not in capsule
    assert 'data-tenant-native-cutover-workspace' in cutover
    assert 'data-tenant-capsule-allocation-workspace' in capsule

    # Backward compatible ?view=allocation deep links, no new endpoint or
    # provider authority switch. Each provider mutation stays in its view.
    assert "'provision', 'allocation', 'native-cutover', 'capsule-governance', 'decisions'" in routes
    redirects = (
        ('change_namespace_allocation_route', 'allocation'),
        ('cutover_namespace_allocation_route', 'native-cutover'),
        ('cutover_capsule_tenant_quota_route', 'capsule-governance'),
        ('change_capsule_tenant_quota_route', 'capsule-governance'),
        ('cutover_capsule_shared_allocation_route', 'capsule-governance'),
    )
    for endpoint, view in redirects:
        body = routes.split(f'def {endpoint}(', 1)[1].split('@tenant_bp.', 1)[0]
        if endpoint.startswith('cutover_capsule_') or endpoint == 'change_capsule_tenant_quota_route':
            scope = 'shared-allocation' if endpoint == 'cutover_capsule_shared_allocation_route' else 'tenant-quota'
            expected = (
                f"return redirect(url_for('tenant.namespace_provisioning', view='{view}', capsule_tab='{scope}'))"
            )
        else:
            expected = f"return redirect(url_for('tenant.namespace_provisioning', view='{view}'))"
        assert expected in body
    assert "url_for('tenant.namespace_provisioning')" in routes  # Provision default.


def test_capsule_governance_scope_navigation_is_url_owned() -> None:
    """#3001: scope-specific Capsule controls render one workflow per URL."""
    from jinja2 import Environment

    workspace = _read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    overview = _read('app/templates/kubernetes/tenant/partials/_capsule_governance_overview.html')
    routes = _read('app/kubernetes/tenant/routes.py')
    for source in (workspace, overview):
        Environment(autoescape=True).parse(source)
    assert "content_tabs.render_links('capsule-governance-scope'," in workspace
    assert 'active_capsule_view' in workspace
    assert 'data-tenant-capsule-active-view="{{ active_capsule_view }}"' in workspace
    for key, label in [
        ('overview', 'Overview'),
        ('tenant-quota', 'Tenant Quota'),
        ('shared-allocation', 'Shared Allocation'),
    ]:
        assert f"('{key}', '{label}', " in workspace
        assert f"capsule_tab='{key}'" in workspace
        assert f"active_capsule_view == '{key}'" in workspace
    assert workspace.count('_capsule_governance_overview.html') == 1
    assert workspace.count('_capsule_tenant_quota_cutover.html') == 1
    assert workspace.count('_capsule_shared_allocation_cutover.html') == 1
    assert "hx_target='#namespace-provisioning-workspace'" in workspace
    assert 'data-tenant-capsule-governance-overview' in overview
    assert 'capsule_tenant_quota_managed|length' in overview
    assert 'capsule_tenant_quota_cutover_tenants|length' in overview
    assert 'capsule_shared_tenants|length' in overview
    assert "view='capsule-governance', capsule_tab='tenant-quota'" in overview
    assert "view='capsule-governance', capsule_tab='shared-allocation'" in overview
    assert "request.args.get('capsule_tab')" in routes
    assert "{'overview', 'tenant-quota', 'shared-allocation'}" in routes
    assert 'active_capsule_view=active_capsule_view' in routes
