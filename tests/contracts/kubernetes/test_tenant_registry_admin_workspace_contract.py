from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tenants_page_keeps_summary_above_the_tabbed_workspace() -> None:
    page = read('app/templates/kubernetes/tenant/tenants.html')
    admin = read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    routes = read('app/kubernetes/tenant/routes.py')

    assert "'Multi-Cluster Posture'" in page
    assert "'Tenant Estate'" in page
    assert 'tenant_summary_metrics' in page
    assert "'Governed Administration'" in page
    assert page.index("'Multi-Cluster Posture'") < page.index("'Governed Administration'")
    assert page.index("'Governed Administration'") < page.index('partials/_tenant_admin_workspace.html')

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
    assert "table_ui.table_classes('min-w-[1120px]')" in registry
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
    for icon in ('shield-check', 'boxes', 'users-round', 'key-round'):
        assert f'data-lucide="{icon}"' in setup
    assert 'Cross-Tenant references fail closed.' in setup
    assert 'bg-status-warning-soft' in setup
    assert 'context_guidance_card.html' not in setup
    assert 'open_by_default' not in setup
    assert 'Tenant Lifecycle Contract' in setup
    assert '1 · Lock Identity' in setup
    assert '2 · Revoke Access' in setup
    assert '3 · Remove Namespaces' in setup
    assert '4 · Decommission' in setup
    assert 'Change strategy:' in setup

    tenant_form = read('app/templates/kubernetes/tenant/partials/_tenant_form.html')
    assert 'components/info_tip.html' in tenant_form
    assert 'tenant-setup-form-tip' in tenant_form
    assert 'Optional. KAORI derives a lowercase slug' not in tenant_form


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
    assert 'components/info_tip.html' in workspace
    assert 'membership-user-tip' in workspace
    assert 'membership-group-tip' in workspace
    assert 'membership-attach-group-tip' in workspace
    assert workspace.count('hx-target="#tenant-admin-workspace"') >= 3
    assert workspace.count('hx-select="#tenant-admin-workspace"') >= 3
    assert workspace.count('hx-disabled-elt="find button"') >= 3
    assert 'bg-status-warning-soft' in workspace
    assert 'Scope Safety' in workspace

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
    assert 'components/info_tip.html' in workspace
    assert 'access-grant-form-tip' in workspace
    assert 'Governance note.' in workspace
    assert 'hx-target="#tenant-admin-workspace"' in workspace
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
    assert 'Delivery Contract' not in workspace
    assert 'human-credential-tip' in workspace
    assert 'deployer-credential-tip' in workspace
    assert '_credential_registry.html' in workspace

    assert "'Credential Lifecycle'" in registry
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.footer' in registry
    assert 'components/info_tip.html' in workspace
    assert 'human-credential-tip' in workspace
    assert 'deployer-credential-tip' in workspace
    assert workspace.count('hx-target="#tenant-admin-workspace"') >= 2
    assert "table_ui.table_classes('min-w-[760px] table-fixed lg:min-w-0')" in registry
    assert 'min-w-[1180px]' not in registry
    assert 'Type / Delivery' in registry
    assert 'Owner / Delivery' not in registry
    for action in ('Renew', 'Suspend', 'Resume', 'Revoke'):
        assert action in registry
    assert 'def get_credential_registry_context(' in read_model


def test_namespace_access_is_a_paginated_non_secret_registry() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html')
    registry = read('app/templates/kubernetes/tenant/partials/_namespace_access_registry.html')
    read_model = read('app/kubernetes/tenant/admin_workspace.py')

    assert 'Effective Namespace Access' in workspace
    assert 'Security Boundary' in workspace
    assert 'components/info_tip.html' in workspace
    assert 'namespace-access-tip' in workspace
    assert 'Derived Evidence' in workspace
    assert 'Credential Context' in workspace
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








def test_tenant_registry_shortcuts_use_local_anchors_without_page_reload() -> None:
    memberships = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    membership_registry = read('app/templates/kubernetes/tenant/partials/_membership_registry.html')
    group_registry = read('app/templates/kubernetes/tenant/partials/_group_registry.html')
    grant_registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    credential_registry = read('app/templates/kubernetes/tenant/partials/_credential_registry.html')

    assert 'id="add-user-membership-form"' in memberships
    assert 'id="create-tenant-group-form"' in memberships
    assert 'id="add-group-membership-form"' in memberships

    assert "'#add-user-membership-form'" in membership_registry
    assert "'#create-tenant-group-form'" in group_registry
    assert "'#access-grant-form'" in grant_registry
    assert "'#credential-issuance'" in credential_registry

    for template in (membership_registry, group_registry, grant_registry, credential_registry):
        assert "~ '#" not in template

def test_tenant_workspace_mutations_preserve_nested_scroll_and_do_not_push_history() -> None:
    partials = (
        'app/templates/kubernetes/tenant/partials/_tenant_form.html',
        'app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html',
        'app/templates/kubernetes/tenant/partials/_membership_registry.html',
        'app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html',
        'app/templates/kubernetes/tenant/partials/_access_grant_registry.html',
        'app/templates/kubernetes/tenant/partials/_tenant_credentials_workspace.html',
        'app/templates/kubernetes/tenant/partials/_credential_registry.html',
    )

    for path in partials:
        template = read(path)
        if 'hx-post=' not in template:
            continue
        assert 'hx-target="#tenant-admin-workspace"' in template
        assert 'hx-select="#tenant-admin-workspace"' in template
        assert 'outerHTML show:none focus-scroll:false' in template
        assert 'hx-push-url=' not in template

    admin = read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    assert "hx_swap='outerHTML show:none focus-scroll:false'" in admin


def test_overview_adds_section_hierarchy_above_tenant_estate() -> None:
    overview = read('app/templates/kubernetes/tenant/overview.html')

    assert "'Governance Scope'" in overview
    assert "'Tenant Estate'" in overview
    assert overview.index("'Governance Scope'") < overview.index("'Tenant Estate'")


def test_access_grant_scope_rule_is_neutral_and_form_geometry_is_balanced() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')

    assert 'Tenant scope uses no target. Environment or Namespace scope requires exactly one matching target.' in workspace
    assert 'xl:grid-cols-6' in workspace
    assert workspace.count('xl:col-span-2') >= 3
    assert workspace.count('xl:col-span-3') >= 2
    assert 'border-outline-subtle bg-surface-elevated' in workspace
    assert 'Governed reconciliation.' in workspace



def test_tenant_identity_is_immutable_and_htmx_feedback_uses_oob_toast() -> None:
    routes = read('app/kubernetes/tenant/routes.py')
    service = read('app/kubernetes/tenant/service.py')
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')
    setup = read('app/templates/kubernetes/tenant/partials/_tenant_setup_workspace.html')
    readme = read('app/kubernetes/tenant/README.md')

    decommission = read('app/kubernetes/tenant/decommission_service.py')

    assert 'def update_tenant_metadata_route(' not in routes
    assert 'def update_tenant_metadata_committed(' not in service
    assert 'def decommission_tenant_route(' in routes
    assert 'request_tenant_decommission_committed' in routes
    assert 'execute_tenant_decommission' in decommission
    assert "tenant.lifecycle_status = TenantLifecycleStatus.DECOMMISSIONING.value" in decommission
    assert 'Update Tenant Metadata' not in setup
    assert 'Tenant Lifecycle Contract' in setup
    assert 'Tenant identity is intentionally immutable after creation.' in setup
    assert 'governed namespace deprovisioning must complete' in setup.lower()
    assert 'Immutable' in registry
    assert 'square-pen' not in registry
    assert 'Decommission' in registry
    assert 'destructive_confirmation_modal.html' in registry
    assert 'data-destructive-modal-open' in registry

    assert 'g.tenant_operational_feedback = feedback' in routes
    assert 'toast_oob=True' in routes
    assert 'components/operational_toast.html' in routes
    assert 'queue_feedback=(not is_htmx)' in routes

    assert 'Tenant identity is immutable after creation' in readme
    assert '#735' in readme
    assert 'database-only lifecycle flag' in readme


def test_cluster_estate_uses_compact_fixed_row_geometry() -> None:
    estate = read('app/templates/kubernetes/tenant/partials/_cluster_estate.html')

    assert "table_ui.table_classes('min-w-[860px] table-fixed')" in estate
    for width in ('w-[34%]', 'w-[12%]', 'w-[14%]', 'w-[18%]', 'w-[22%]'):
        assert width in estate
    assert estate.count('align-middle') >= 5
    assert 'Governed Tenants' in estate
    assert 'Managed Namespaces' in estate
    assert 'ml-auto' not in estate


def test_tenant_access_grant_links_namespace_creation_and_keeps_guidance_neutral() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')

    assert "Create Namespace" in workspace
    assert "url_for('tenant.namespace_provisioning')" in workspace
    assert "Tenant scope uses no target. Environment or Namespace scope requires exactly one matching target." in workspace
    assert "bg-surface-elevated" in workspace
    assert "bg-status-info-soft" not in workspace


def test_namespace_access_security_boundary_matches_peer_surface() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html')

    assert "Security Boundary" in workspace
    assert workspace.count('class="flex gap-3 bg-surface-card p-4"') >= 3
    assert "text-content-muted" in workspace
    assert "bg-status-info-soft" not in workspace


def test_operational_attention_peer_cards_are_geometry_symmetric() -> None:
    overview = read('app/templates/kubernetes/tenant/overview.html')

    assert "xl:items-stretch" in overview
    assert overview.count("extra_classes='flex h-full flex-col'") >= 2
    assert overview.count("body_classes='flex flex-1 flex-col p-0'") >= 2
    assert "Showing {{ tenant_attention_rows|length }} prioritized condition" in overview
    assert "Showing {{ tenant_recent_activity_rows|length }} latest committed event" in overview

def test_kaori_info_tip_is_a_reusable_hover_and_focus_standard() -> None:
    component = read('app/templates/components/info_tip.html')
    docs = read('docs/design/components/INFO_TIP.md')

    assert 'macro render(id, title, text=' in component
    assert 'aria-describedby="{{ id }}"' in component
    assert 'role="tooltip"' in component
    assert 'group-hover:visible' in component
    assert 'group-focus-within:visible' in component
    assert 'focus-visible:ring-2' in component

    assert 'compact guidance pattern' in docs
    assert 'pointer hover and keyboard/touch focus' in docs
    assert 'Do **not** hide validation errors' in docs

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



def test_governed_tenant_decommission_is_async_provider_verified_and_fail_closed() -> None:
    decommission = read('app/kubernetes/tenant/decommission_service.py')
    provisioning = read('app/kubernetes/tenant/provisioning.py')
    tasks = read('app/kubernetes/tenant/tasks.py')
    adapter = read('app/kubernetes/tenant/job_adapter.py')
    config = read('app/config/default.py')
    models = read('app/models/tenant.py')
    migration = read('migrations/versions/20260928_tenant_decommission.py')

    ordered_markers = [
        "stage = 'credentials'",
        "stage = 'access_grants'",
        "stage = 'memberships'",
        "stage = 'policy_cleanup'",
        "stage = 'namespaces'",
        "stage = 'provider_verification'",
        "stage = 'finalize'",
    ]
    offsets = [decommission.index(marker) for marker in ordered_markers]
    assert offsets == sorted(offsets)

    assert 'Capsule is authoritative for this Tenant.' in decommission
    assert 'will not bypass Capsule with direct Native Kubernetes deletion' in decommission
    assert "tenant.provider_key != 'native_kubernetes'" in provisioning
    assert "tenant.reconciliation_authority != 'native_kubernetes'" in provisioning
    assert 'api.delete_namespace(name=record.namespace)' in provisioning
    assert '_namespace_delete_observation' in provisioning
    assert 'Finalizers:' in provisioning
    assert 'force' not in provisioning[provisioning.index('def deprovision_native_namespace('):provisioning.index('def deprovision_native_namespace_committed(')]

    assert "name='app.kubernetes.tenant.tasks.decommission_tenant'" in tasks
    assert 'dispatch_tenant_decommission' in adapter
    assert "workload_class=WORKLOAD_RUNTIME" in adapter
    assert "INTEGRATION_RUNTIME_CELERY_QUEUE" in adapter
    assert "'app.kubernetes.tenant.tasks.decommission_tenant'" in config

    assert "DEPROVISIONING = 'deprovisioning'" in models
    assert "DEPROVISIONED = 'deprovisioned'" in models
    assert 'generation: Mapped[int]' in models
    assert 'uq_tenants_cluster_slug_generation' in migration
