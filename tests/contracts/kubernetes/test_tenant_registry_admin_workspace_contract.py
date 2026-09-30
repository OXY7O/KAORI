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

    assert 'components/numbered_governance_steps.html' in setup
    assert 'Tenant Governance Flow' in setup
    for label in ('Create Tenant', 'Provision Namespace', 'Add Membership', 'Apply Access Grant', 'Issue Credential'):
        assert label in setup
    assert 'Important Boundaries' in setup
    for icon in ('shield-check', 'boxes', 'users-round', 'key-round'):
        assert f'data-lucide="{icon}"' in setup
    assert 'Cross-Tenant references are blocked.' in setup
    assert 'bg-status-warning-soft' in setup
    assert 'xl:items-stretch' in setup
    assert 'xl:grid-rows-[auto_1fr]' in setup
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
    assert 'flex h-full flex-col overflow-visible' in tenant_form
    assert 'Create the Tenant boundary first; namespace and access follow.' in tenant_form
    assert 'rounded-b-xl border-t border-outline-subtle bg-surface-hover' in tenant_form
    assert 'Optional. KAORI derives a lowercase slug' not in tenant_form


def test_memberships_use_symmetric_actions_and_scalable_registries() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    memberships = read('app/templates/kubernetes/tenant/partials/_membership_registry.html')
    groups = read('app/templates/kubernetes/tenant/partials/_group_registry.html')
    read_model = read('app/kubernetes/tenant/admin_workspace.py')

    assert 'Membership Model' in workspace
    assert 'components/numbered_governance_steps.html' in workspace
    assert "layout='compact-grid'" in workspace
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

    assert 'components/info_tip.html' in memberships
    assert 'tenant-membership-lifecycle-tip' in memberships
    assert 'title_extra=title_info' in memberships
    assert "button_text='Membership Guide'" not in memberships
    assert 'tenant-group-lifecycle-tip' in groups
    assert 'title_extra=title_info' in groups
    assert "button_text='Group Guide'" not in groups

    assert 'def get_membership_registry_context(' in read_model
    assert 'def get_group_registry_context(' in read_model
    assert 'paginate_query(' in read_model


def test_access_grants_use_setup_style_form_guidance_and_full_registry() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    read_model = read('app/kubernetes/tenant/admin_workspace.py')

    assert 'id="access-grant-form"' in workspace
    assert 'xl:col-span-5' in workspace
    assert 'grid h-full gap-5 xl:col-span-7 xl:grid-rows-[auto_1fr]' in workspace
    assert 'Access Grant Flow' in workspace
    assert 'Access scope guide' in workspace
    assert 'Namespace Scope' in workspace
    assert 'Environment Scope' in workspace
    assert 'Tenant Scope' in workspace
    assert 'Membership fixes the Tenant boundary.' not in workspace
    assert 'Targets are filtered automatically.' not in workspace
    assert 'Effective RBAC remains provider-verified.' not in workspace
    assert 'Tenant and scope are validated before commit.' in workspace
    assert 'Namespace needs one target; broader scopes reconcile as namespaces become available.' in workspace
    assert 'grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3' in workspace
    assert 'Start from one active Membership that identifies the principal and fixes its Tenant boundary.' in workspace
    assert (
        'Use the least-privilege profile and narrowest scope that meets the principal’s operational need.' in workspace
    )
    assert 'Environment/Tenant scope may stay Pending until a namespace exists.' in workspace
    assert 'Access Boundaries' in workspace
    assert 'components/info_tip.html' in workspace
    assert 'access-grant-form-tip' in workspace
    assert 'access-profile-tip' in workspace
    assert 'access-scope-tip' in workspace
    assert 'data-access-membership' in workspace
    assert 'data-access-scope-guidance' in workspace
    assert 'data-access-environment-field' in workspace
    assert 'data-access-namespace-field' in workspace
    assert 'data-tenant-id="{{ membership.tenant_id }}"' in workspace
    assert 'data-tenant-id="{{ environment.tenant_id }}"' in workspace
    assert 'data-tenant-id="{{ namespace.environment.tenant_id }}"' in workspace
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
    assert 'table_ui.action_grid_classes(2)' in registry
    assert 'flex flex-wrap justify-end gap-1.5' not in registry
    assert 'Type / Delivery' in registry
    assert 'Owner / Delivery' not in registry
    for action in ('Renew', 'Suspend', 'Resume', 'Revoke'):
        assert action in registry
    assert 'components/one_time_secret.html' in registry
    assert 'data-credential-material-open' in registry
    assert 'Reveal Token' in registry
    assert 'Generate Kubeconfig' in registry
    assert 'data-credential-material-namespace' in registry
    assert 'data-credential-material-ttl' in registry
    assert 'credential_delivery_targets' in read_model
    assert 'credential_delivery_policies' in read_model
    assert 'credential_material_ttl_choices' in read_model
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


def test_tenant_card_guidance_is_title_adjacent_and_hover_overflow_is_visible() -> None:
    tenant_form = read('app/templates/kubernetes/tenant/partials/_tenant_form.html')
    memberships = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    grants = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    credentials = read('app/templates/kubernetes/tenant/partials/_tenant_credentials_workspace.html')
    namespace_access = read('app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html')

    for title, tip_id, source in (
        ('Add Tenant', 'tenant-setup-form-tip', tenant_form),
        ('Add User Membership', 'membership-user-tip', memberships),
        ('Create Tenant Group', 'membership-group-tip', memberships),
        ('Add Group Membership', 'membership-attach-group-tip', memberships),
        ('Apply Access Grant', 'access-grant-form-tip', grants),
        ('Issue Human Access', 'human-credential-tip', credentials),
        ('Issue CI/CD Deployer', 'deployer-credential-tip', credentials),
        ('Effective Namespace Access', 'namespace-access-tip', namespace_access),
    ):
        title_index = source.index(title)
        tip_index = source.index(tip_id)
        assert abs(title_index - tip_index) < 1200, (title, tip_id)

    assert 'flex h-full flex-col overflow-visible' in tenant_form
    assert memberships.count('flex h-full flex-col overflow-visible') >= 3
    assert 'flex h-full flex-col overflow-visible' in grants
    assert credentials.count('flex h-full flex-col overflow-visible') >= 2
    assert 'overflow-visible rounded-xl' in namespace_access

    # Field-specific guidance remains allowed when semantics are unique to the field.
    assert 'capsule-owner-kind-tip' in tenant_form
    assert 'capsule-owner-subject-tip' in tenant_form
    assert 'access-profile-tip' in grants
    assert 'access-scope-tip' in grants


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


def test_access_grant_uses_tenant_setup_two_card_composition() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')

    assert 'xl:grid-cols-12' in workspace
    assert 'xl:col-span-5' in workspace
    assert 'grid h-full gap-5 xl:col-span-7 xl:grid-rows-[auto_1fr]' in workspace
    assert 'Access Grant Flow' in workspace
    assert 'Access Boundaries' in workspace
    assert 'Tenant uses no target. Environment or Namespace requires exactly one matching target.' in workspace
    assert 'Provider Authority' in workspace
    assert 'Secret Boundary' in workspace
    assert 'Tenant and scope are validated before commit.' in workspace


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
    assert 'tenant.lifecycle_status = TenantLifecycleStatus.DECOMMISSIONING.value' in decommission
    assert 'Update Tenant Metadata' not in setup
    assert 'Tenant Lifecycle Contract' in setup
    assert 'Tenant identity is intentionally immutable after creation.' in setup
    assert 'governed namespace deprovisioning must complete' in setup.lower()
    assert 'Immutable' in registry
    assert 'square-pen' not in registry
    assert 'Decommission' in registry
    assert 'destructive_confirmation_modal.html' in registry
    assert 'data-destructive-modal-open' in registry
    assert 'Freeze Mutations' in registry
    assert 'Remove Namespaces' in registry
    assert 'Verify & Retain' in registry
    assert 'Terminating' in registry

    assert 'g.tenant_operational_feedback = feedback' in routes
    assert 'toast_oob=True' in routes
    assert 'components/operational_toast.html' in routes
    assert 'queue_feedback=(not is_htmx)' in routes

    assert 'Tenant identity is immutable after creation' in readme
    assert '#735' in readme
    assert 'database-only lifecycle flag' in readme


def test_cluster_estate_uses_compact_shared_table_geometry() -> None:
    estate = read('app/templates/kubernetes/tenant/partials/_cluster_estate.html')

    assert "table_ui.table_classes('min-w-[900px]')" in estate
    assert 'table_ui.cluster_identity(row.name, row.environment)' in estate
    for width in ('w-[29%]', 'w-[11%]', 'w-[13%]', 'w-[16%]', 'w-[17%]', 'w-[14%]'):
        assert width in estate
    assert estate.count('align-middle') >= 6
    assert '>Actions</th>' in estate
    assert 'header_cell_classes(action=true)' in estate
    assert 'Open Capacity' in estate
    assert 'table_ui.action_classes()' in estate
    assert 'whitespace-nowrap' in estate
    assert 'chart-no-axes-combined' in estate
    assert 'Governed Tenants' in estate
    assert 'Managed Namespaces' in estate


def test_tenant_access_grant_links_namespace_creation_and_keeps_guidance_neutral() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')

    assert 'Create Namespace' in workspace
    assert "url_for('tenant.namespace_provisioning')" in workspace
    assert 'Tenant uses no target. Environment or Namespace requires exactly one matching target.' in workspace
    assert 'Access Boundaries' in workspace
    assert 'bg-status-info-soft' not in workspace


def test_namespace_access_security_boundary_matches_peer_surface() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_namespace_access_workspace.html')

    assert 'Security Boundary' in workspace
    assert workspace.count('class="flex gap-3 bg-surface-card p-4"') >= 3
    assert 'text-content-muted' in workspace
    assert 'bg-status-info-soft' not in workspace


def test_operational_attention_peer_cards_preserve_bounded_alignment() -> None:
    overview = read('app/templates/kubernetes/tenant/overview.html')

    assert 'xl:items-start' in overview
    assert overview.count("extra_classes='flex h-full flex-col'") >= 2
    assert overview.count("body_classes='flex flex-1 flex-col p-0'") >= 2
    assert 'Showing {{ tenant_attention_rows|length }} prioritized condition' in overview
    assert 'Showing {{ tenant_recent_activity_rows|length }} latest committed event' in overview


def test_kaori_info_tip_uses_desktop_hover_and_native_dialog_activation() -> None:
    component = read('app/templates/components/info_tip.html')
    docs = read('docs/design/components/INFO_TIP.md')

    assert (
        "macro render(id, title, text='', items=None, placement='left', button_text=None, button_classes=None)"
        in component
    )
    assert 'data-kaori-dialog-open' in component
    assert 'data-dialog-target="{{ id }}-dialog"' in component
    assert 'aria-haspopup="dialog"' in component
    assert 'dialog id="{{ id }}-dialog"' in component
    assert 'data-kaori-native-dialog' in component
    assert 'role="tooltip"' in component
    assert 'sm:group-hover:block' in component
    assert 'group-focus-within:block' not in component
    assert 'fixed inset-x-4 bottom-4' not in component
    assert 'button_classes if button_classes else action_button.classes' in component
    assert 'focus-visible:ring-2' in component
    assert 'h-6 w-6' in component
    assert 'circle-help' in component

    assert 'desktop pointer hover' in docs
    assert 'click, touch, or keyboard activation' in docs
    assert 'native `<dialog>` top layer' in docs
    assert 'table_ui.action_classes()' in docs
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
    workspace = read('app/kubernetes/tenant/workspace.py')

    assert overview.count('min-h-[7.5rem]') >= 3
    assert 'Committed governance finding' in overview
    assert 'Recent Tenant Activity' in overview
    assert 'Needs Attention' in overview
    assert 'def _tenant_attention_rows(findings: list[dict[str, Any]], *, limit: int = 3)' in workspace
    assert 'def _tenant_recent_activity(*, limit: int = 3)' in workspace
    assert 'h-[calc(100%+1rem)]' not in overview
    assert '<ol class="flex-1 divide-y divide-outline-subtle">' in overview


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
        "stage = 'managed_resources'",
        "stage = 'namespaces'",
        "stage = 'policy_cleanup'",
        "stage = 'provider_verification'",
        "stage = 'finalize'",
    ]
    offsets = [decommission.index(marker) for marker in ordered_markers]
    assert offsets == sorted(offsets)

    capsule = read('app/kubernetes/tenant/capsule_tenant.py')

    assert 'delete_capsule_tenant_verified' in decommission
    assert "tenant.provider_state == 'capsule'" in decommission
    assert "tenant.reconciliation_authority == 'capsule'" in decommission
    assert "provider_evidence.get('created_by_kaori')" in decommission
    assert 'Baseline Capsule teardown requires zero active Tenant namespace records' in decommission
    assert 'Baseline Capsule teardown requires active Access Grants and credentials to be cleared' in decommission
    assert 'Baseline Capsule teardown requires Tenant-managed provider resources to be cleared first.' in decommission
    assert "tenant.provider_key != 'native_kubernetes'" in provisioning

    assert 'def delete_capsule_tenant_verified(' in capsule
    assert 'labels.get(_MANAGED_BY_KEY) != _MANAGED_BY_VALUE' in capsule
    assert 'labels.get(_TENANT_ID_KEY) != kaori_tenant_id' in capsule
    assert '_TENANT_GENERATION_KEY' in capsule
    assert 'expected_uid and current_uid and current_uid != expected_uid' in capsule
    assert "V1DeleteOptions(propagation_policy='Foreground')" in capsule
    assert 'for _ in range(10)' in capsule
    assert "'provider_verified_absent': True" in capsule
    assert "tenant.reconciliation_authority != 'native_kubernetes'" in provisioning
    assert 'api.delete_namespace(name=record.namespace)' in provisioning
    assert '_namespace_delete_observation' in provisioning
    assert 'Finalizers:' in provisioning
    teardown_start = provisioning.index('def deprovision_native_namespace(')
    teardown_end = provisioning.index('def deprovision_native_namespace_committed(')
    teardown = provisioning[teardown_start:teardown_end]
    assert 'api.delete_namespace(name=record.namespace)' in teardown
    assert 'finalizers = []' not in teardown
    assert 'patch_namespace' not in teardown

    assert "name='app.kubernetes.tenant.tasks.decommission_tenant'" in tasks
    assert 'dispatch_tenant_decommission' in adapter
    assert 'require_registered_worker=True' in adapter
    assert 'workload_class=WORKLOAD_RUNTIME' in adapter
    assert 'INTEGRATION_RUNTIME_CELERY_QUEUE' in adapter
    assert "'app.kubernetes.tenant.tasks.decommission_tenant'" in config

    assert "DEPROVISIONING = 'deprovisioning'" in models
    assert "DEPROVISIONED = 'deprovisioned'" in models
    assert 'generation: Mapped[int]' in models
    assert 'uq_tenants_cluster_slug_generation' in migration


def test_tenant_registry_distinguishes_active_namespaces_from_retained_history() -> None:
    service = read('app/kubernetes/tenant/service.py')
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')

    assert 'namespace_history_count_map' in service
    assert 'TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in service
    assert "'namespace_history_count': namespace_history_count_map.get(item.id, 0)" in service
    assert 'historical namespace record' in registry
    assert 'Active managed namespaces' in registry


def test_destructive_modal_supports_structured_impact_summary() -> None:
    component = read('app/templates/components/destructive_confirmation_modal.html')

    assert 'impact_items=none' in component
    assert 'warning=none' in component
    assert 'What will happen' in component
    assert 'data-destructive-modal-title' in component
    assert 'data-destructive-detail' in component
    assert 'data-destructive-action-label' in component


def test_committed_tenant_snapshot_is_separate_from_lazy_live_provider_connectivity() -> None:
    routes = read('app/kubernetes/tenant/routes.py')
    live_service = read('app/kubernetes/tenant/live_connection.py')
    live_partial = read('app/templates/kubernetes/tenant/partials/_live_connection_snapshot.html')
    live_loader = read('app/templates/kubernetes/tenant/partials/_live_connection_loader.html')
    committed_partial = read('app/templates/kubernetes/tenant/partials/_collection_snapshot_context.html')
    sync_workspace = read('app/templates/kubernetes/tenant/partials/_sync_workspace.html')
    base = read('app/templates/kubernetes/tenant/base.html')
    service = read('app/kubernetes/tenant/service.py')

    assert 'version_api().get_code(_request_timeout=3)' in live_service
    assert "@tenant_bp.get('/live-provider-connectivity')" in routes
    assert "render_template(\n            'kubernetes/tenant/partials/_live_connection_snapshot.html'" in routes
    assert "context.update(get_live_tenant_connection_context())" not in routes

    assert "title='Live Provider Connectivity'" in live_partial
    assert 'Live probe; not committed inventory' in live_partial
    assert 'Provider operations fail closed per target' in live_partial
    assert 'tenant-live-provider-connectivity' in live_partial

    assert 'hx-get="{{ url_for(\'tenant.live_provider_connectivity\') }}"' in live_loader
    assert 'hx-trigger="load"' in live_loader
    assert 'Committed KAORI Tenant state is already loaded.' in live_loader
    assert "title='Live Provider Connectivity'" in live_loader

    assert "title='Tenant Collection Snapshot'" in committed_partial
    assert 'Committed Tenant snapshot evidence' in committed_partial
    assert "latest_label='Last Successful'" in committed_partial
    assert "scope_metric_label='Committed Scope'" in committed_partial
    assert '_collection_snapshot_context.html' in sync_workspace

    assert '_collection_snapshot_context.html' in base
    assert '_live_connection_loader.html' in base
    assert '{% block tenant_content %}' in base
    assert '{% if not native_available %}\n            {% include "components/cluster/_onboarding_banner.html" %}' not in base
    assert 'Provider Operations Restricted' in base
    assert 'Committed KAORI Tenant state remains available.' in base

    assert 'registered_clusters = (' in service
    assert "for cluster in registered_clusters" in service
    assert "'registered_clusters': registered_clusters" in service


def test_tenant_discovery_reads_provider_live_and_adopts_only_after_human_preflight() -> None:
    routes = read('app/kubernetes/tenant/routes.py')
    admin = read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    service = read('app/kubernetes/tenant/discovery_service.py')
    template = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    preflight = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    preflight_error = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight_error.html')
    modal_js = read('app/static/js/tenant_adoption_modal.js')

    assert "'discovery'" in routes
    assert 'get_tenant_discovery_context' in routes
    assert 'adopt_discovered_tenant_committed' in routes
    assert "('discovery', 'Discovery', 'radar'" in admin
    assert '_tenant_discovery.html' in admin

    assert 'list_namespace(_request_timeout=5)' in service
    assert 'list_cluster_custom_object(' in service
    assert 'get_cluster_custom_object(' in service
    assert "'capsule.clastix.io'" in service
    assert "'native_kubernetes'" in service
    assert "'Discovered'" in service
    assert "'Managed'" in service
    assert "'Blocked'" in service

    # Discovery/adoption may create KAORI database records, but it must never
    # create, patch, or delete provider objects.
    for provider_mutation in (
        'create_namespace(',
        'patch_namespace(',
        'delete_namespace(',
        'create_cluster_custom_object(',
        'patch_cluster_custom_object(',
        'delete_cluster_custom_object(',
    ):
        assert provider_mutation not in service
    assert "'provider_mutation_performed': False" in service
    assert 'TenantOwnershipStatus.ADOPTED.value' in service

    assert 'Tenant Discovery' in template
    assert 'Live Status' in template
    assert 'KAORI Classification' in template
    assert 'Governed Tenant' in template
    # Discovery registry stays lightweight. Deep allocation/capability inspection
    # is loaded only after the operator explicitly requests Adoption Preflight.
    discovery_context_source = service.split('def get_tenant_adoption_preflight_context', 1)[0]
    assert 'observe_native_namespace_allocation(' not in discovery_context_source
    assert 'observe_capsule_tenant_allocation(' not in discovery_context_source
    assert 'discover_capsule(' not in discovery_context_source
    assert 'def get_tenant_adoption_preflight_context' in service
    assert "@tenant_bp.get('/discovery/preflight')" in routes
    assert 'get_tenant_adoption_preflight_context' in routes

    assert 'data-tenant-adoption-load' in template
    assert 'tenant.tenant_adoption_preflight_route' in template
    assert 'hx-target="#tenant-adoption-preflight-slot"' in template
    assert 'id="tenant-adoption-preflight-slot"' in template
    assert 'data-tenant-adoption-modal' not in template

    assert 'Adoption Preflight' in preflight
    assert 'Adoption Decision' in preflight
    assert 'Adoption Impact' in preflight
    assert 'KAORI records' in preflight
    assert 'Provider remains authoritative' in preflight
    assert 'After adoption' in preflight
    assert 'Provider &amp; Live Context' in preflight
    assert 'Allocation Overview' in preflight
    assert 'Effective Allocation' in preflight
    assert 'Live provider values' in preflight
    assert 'max-w-[1360px]' in preflight
    assert "lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.15fr)]" in preflight
    assert "lg:grid-cols-[minmax(0,1.35fr)_minmax(460px,1fr)]" in preflight
    assert 'grid-cols-3 gap-px border-t border-outline-subtle bg-outline-subtle' in preflight
    assert 'grid gap-px bg-outline-subtle sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5' in preflight
    assert "'requests.cpu': 'CPU Requests'" in preflight
    assert "'limits.cpu': 'CPU Limits'" in preflight
    assert "'requests.memory': 'Memory Requests'" in preflight
    assert "'limits.memory': 'Memory Limits'" in preflight
    assert "'pods': 'Pods'" in preflight
    assert "{% set quota_order = [" in preflight
    assert "{% for key in quota_order if key in allocation.shared_quota %}" in preflight
    assert 'Observed allocation contains unsupported or ambiguous dimensions; governance cutover must fail closed.' in preflight
    assert 'Namespace Coverage' in preflight
    assert 'Proposed KAORI Mapping' in preflight
    assert 'Adoption Result' in preflight
    assert 'Governance Checks' in preflight
    assert 'Technical Evidence' in preflight
    assert 'Human confirmation.' in preflight
    assert 'No provider mutation.' in preflight
    assert 'Adopt as Observed' in preflight
    assert 'Adopt as' in preflight
    assert 'remains authoritative' in preflight
    assert 'Commits identity, provider lineage, Namespace evidence, and observed allocation.' in preflight
    assert 'Read-only until governance cutover.' in preflight
    assert 'Next: review governance cutover.' in preflight
    assert 'tenant-adoption-control-tip' in preflight
    assert 'Allocation control' in preflight

    assert 'components/info_tip.html' in template
    assert 'components/status_detail_dialog.html' not in template
    assert 'tenant-discovery-status-tip' in template
    assert 'tenant-discovery-live-' not in template
    assert 'tenant-discovery-classification-' not in template
    assert 'tenant-discovery-action-' not in template
    assert 'Discovery status' in template
    assert 'Provider Missing' in template
    assert "page_param='discovery_page'" in template
    assert "per_page_param='discovery_per_page'" in template

    assert 'Adoption Preflight Unavailable' in preflight_error
    assert 'No KAORI or provider state was changed' in preflight_error

    assert 'data-tenant-adoption-load' in modal_js
    assert 'tenant-adoption-preflight-slot' in modal_js
    assert 'htmx:afterSwap' in modal_js
    assert 'data-tenant-adoption-close' in modal_js
    assert 'htmx:afterRequest' in modal_js


def test_decommissioned_tenant_and_namespace_identity_can_be_recreated_as_new_generation() -> None:
    models = read('app/models/tenant.py')
    service = read('app/kubernetes/tenant/service.py')
    migration = read('migrations/versions/20260928_tenant_namespace_generation.py')

    assert "UniqueConstraint('cluster_id', 'slug', 'generation'" in models
    assert 'prior_generations' in service
    assert 'TenantLifecycleStatus.DECOMMISSIONED.value' in service
    assert 'generation = max(' in service

    assert 'generation: Mapped[int]' in models
    assert 'prior_namespace_generations' in service
    assert 'TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in service
    assert 'record.generation = namespace_generation' in service
    assert 'uq_tenant_namespaces_cluster_namespace_generation' in migration


def test_same_tenant_slug_is_scoped_by_cluster() -> None:
    models = read('app/models/tenant.py')
    service = read('app/kubernetes/tenant/service.py')

    assert "UniqueConstraint('cluster_id', 'slug', 'generation'" in models
    assert 'Tenant.query.filter_by(cluster_id=cluster.id, slug=slug)' in service


def test_tenant_estate_header_does_not_repeat_pagination_summary() -> None:
    estate = read('app/templates/kubernetes/tenant/partials/_cluster_estate.html')

    assert 'Committed Tenant posture by cluster.' in estate
    assert 'Compact Tenant posture from committed evidence.' not in estate


def test_live_provider_connectivity_uses_compact_non_snapshot_copy() -> None:
    partial = read('app/templates/kubernetes/tenant/partials/_live_connection_snapshot.html')
    service = read('app/kubernetes/tenant/live_connection.py')

    assert 'Live probe; not committed inventory' in partial
    assert 'Registered Kubernetes connections' in partial
    assert 'Provider operations fail closed per target' in partial
    assert 'Live API reachability' in service
    assert 'Committed KAORI Tenant state remains readable' in service
    assert "title='Tenant Collection Snapshot'" not in partial


def test_tenant_status_actions_use_semantic_labels() -> None:
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')

    assert "special_label('Already Managed', 'normal', 'shield-check')" in discovery
    assert 'Review Adoption' in discovery
    assert "special_label('Candidate', 'info', 'radar')" in discovery
    assert "special_label('Blocked', 'critical', 'shield-alert')" in discovery
    assert 'tenant-discovery-status-tip' in discovery
    assert 'status_detail_dialog' not in discovery

    assert "special_label('History Retained', 'unknown', 'archive')" in registry
    assert "special_label('Blocked', 'critical', 'shield-alert')" in registry
    assert 'tenant-registry-status-tip' in registry
    assert 'Blocked — Tenant stays valid; teardown fails closed until blockers clear.' in registry
    assert 'status_detail_dialog' not in registry
    assert "special_label('Unavailable', 'unknown', 'circle-slash-2')" in registry


def test_tenant_setup_explains_capsule_adoption_boundary() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_tenant_form.html')
    setup = read('app/templates/kubernetes/tenant/partials/_tenant_setup_workspace.html')

    assert '<option value="native_kubernetes" selected>Native Kubernetes</option>' in form
    assert '<option value="capsule">Capsule</option>' in form
    assert 'Existing Capsule Tenant CRs use Discovery → Adoption.' in form
    assert 'Native Kubernetes and supported Capsule clusters allow direct creation.' in setup
    assert 'Existing Capsule Tenant CRs use Discovery → Adoption.' in setup


def test_tenant_sync_marks_fresh_missing_namespaces_as_observational_drift() -> None:
    sync = read('app/kubernetes/tenant/sync_service.py')
    tasks = read('app/kubernetes/tenant/tasks.py')
    service = read('app/kubernetes/tenant/service.py')
    routes = read('app/kubernetes/tenant/routes.py')
    operations = read('app/templates/kubernetes/tenant/operations.html')
    drift_registry = read('app/templates/kubernetes/tenant/partials/_operations_drift_registry.html')

    assert 'def apply_missing_namespace_drift_from_inventory()' in sync
    assert 'TenantNamespaceProvisioningStatus.READY.value' in sync
    assert 'TenantNamespaceProvisioningStatus.DRIFTED.value' in sync
    assert 'source_inventory_cutoff' in sync
    assert 'cutoff < anchor' in sync
    assert "observed_absent': True" in sync
    assert "source': 'committed_kubernetes_inventory'" in sync
    assert 'create_namespace(' not in sync
    assert 'patch_namespace(' not in sync
    assert 'delete_namespace(' not in sync

    assert 'apply_missing_namespace_drift_from_inventory()' in tasks
    assert "snapshot['drifted_namespace_count']" in tasks

    assert 'def reconcile_managed_native_namespace_committed(*, namespace_id: int)' in service
    assert 'record.ownership_status != TenantOwnershipStatus.MANAGED.value' in service
    assert "tenant.reconciliation_authority != 'native_kubernetes'" in service
    assert 'reconcile_native_namespace(record)' in service

    assert "@tenant_bp.post('/namespaces/<int:namespace_id>/reconcile')" in routes
    assert 'reconcile_managed_native_namespace_committed(namespace_id=namespace_id)' in routes
    assert "operation': 'reconcile_namespace'" in routes

    assert '_operations_drift_registry.html' in operations
    assert 'Namespace Provider Drift' in drift_registry
    assert "special_label('Drifted', 'warning', 'triangle-alert')" in drift_registry
    assert "url_for('tenant.reconcile_namespace_route', namespace_id=item.id)" in drift_registry
    assert 'Sync observes drift only.' in drift_registry
    assert 'Reconcile' in drift_registry


def test_tenant_setup_enables_capability_gated_capsule_direct_create() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_tenant_form.html')
    service = read('app/kubernetes/tenant/service.py')
    capsule = read('app/kubernetes/tenant/capsule_tenant.py')
    page = read('app/templates/kubernetes/tenant/tenants.html')
    provider_js = read('app/static/js/tenant_setup_provider.js')

    assert 'name="provider_key"' in form
    assert 'value="native_kubernetes"' in form
    assert 'value="capsule"' in form
    assert 'Capsule Initial Owner' in form
    assert 'name="capsule_owner_kind"' in form
    assert 'name="capsule_owner_subject"' in form
    assert '<option value="capsule">Capsule</option>' in form
    assert 'capability checked on submit' not in form
    assert 'capsule-owner-kind-tip' in form
    assert 'capsule-owner-subject-tip' in form
    assert 'Owner Subject is required for every Owner Kind.' in form
    assert 'User example — alice@example.com' in form
    assert 'Group example — oidc:org:platform-team' in form
    assert 'ServiceAccount example — system:serviceaccount:platform:deployer' in form
    assert 'Required for Capsule provider ownership; separate from KAORI Memberships.' in form
    assert 'Existing Capsule Tenant? Use Discovery → Adoption.' in form
    assert 'Capsule capability and admission are validated when Add Tenant is submitted.' in form
    assert 'tenant_setup_provider.js' in page

    assert "_ALLOWED_TENANT_PROVIDERS = {'native_kubernetes', 'capsule'}" in service
    assert 'create_capsule_tenant(' in service
    assert "tenant.reconciliation_authority = 'capsule'" in service
    assert 'compensate_capsule_tenant_create' in service

    assert "dry_run='All'" in capsule
    assert 'discover_capsule(' in capsule
    assert 'CapsuleTenantProvider' in capsule
    assert 'TenantProviderState.CAPSULE' in capsule
    assert 'Use Tenant Discovery → Adoption' in capsule
    assert "'created_by_kaori': True" in capsule
    assert "'secret_material_persisted': False" in capsule

    assert 'data-capsule-owner-fields' in provider_js
    assert 'data-capsule-owner-control' in provider_js


def test_live_discovery_surfaces_missing_managed_provider_objects() -> None:
    service = read('app/kubernetes/tenant/discovery_service.py')
    template = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')

    assert 'observed_native_names' in service
    assert "provider_status': 'Missing'" in service
    assert 'Committed KAORI ownership exists, but the Namespace is missing from the live provider.' in service
    assert 'observed_capsule_names' in service
    assert 'authoritative Capsule Tenant CR is missing' in service
    assert "special_label('Provider Missing', 'critical', 'triangle-alert')" in template


def test_adoption_modal_uses_wide_review_geometry_and_compact_live_copy() -> None:
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    live = read('app/kubernetes/tenant/live_connection.py')

    assert 'max-w-5xl' in discovery
    assert 'md:grid-cols-2 xl:grid-cols-3' in discovery
    assert "description = 'Live Kubernetes API is reachable.'" in live


def test_tenant_setup_uses_compact_cross_tenant_boundary_copy() -> None:
    setup = read('app/templates/kubernetes/tenant/partials/_tenant_setup_workspace.html')

    assert 'Cross-Tenant references are blocked.' in setup
    assert 'Identity, scope, grants, and credentials stay within one Tenant.' in setup
    assert 'Tenant ownership, namespace scope, identity, Access Grants, and credential delivery' not in setup


def test_tenant_group_registry_uses_governed_lifecycle_actions_without_hard_delete() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_group_registry.html')
    tenants = read('app/templates/kubernetes/tenant/tenants.html')
    membership_registry = read('app/templates/kubernetes/tenant/partials/_membership_registry.html')

    assert '>Actions</th>' in registry
    assert 'components/info_tip.html' in registry
    assert 'tenant-group-lifecycle-tip' in registry
    assert 'title_extra=title_info' in registry
    assert "button_text='Group Guide'" not in registry
    assert 'Use Edit for mistakes; Retire removes future use while preserving history.' in registry
    assert 'data-tenant-group-edit-open' in registry
    assert "url_for('tenant.retire_tenant_group_route', group_id=group.id)" in registry
    assert "url_for('tenant.reactivate_tenant_group_route', group_id=group.id)" in registry
    assert 'Edit Tenant Group' in registry
    assert 'Retire Tenant Group' in registry
    assert 'tenant_group_modal.js' in tenants
    assert 'Delete Tenant Group' not in registry
    assert 'hard-delete' not in membership_registry.lower()
    assert 'Revoke/Reactivate' in membership_registry


def test_access_grant_form_filters_targets_and_profiles_from_selected_membership() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    page = read('app/templates/kubernetes/tenant/tenants.html')
    scope_js = read('app/static/js/tenant_access_grant_form.js')
    service = read('app/kubernetes/tenant/access_service.py')

    assert 'data-principal-type="{{ membership.principal_type }}"' in workspace
    assert 'data-provider-key="{{ membership.tenant.provider_key }}"' in workspace
    assert 'data-access-provider-warning' in workspace
    assert 'data-access-submit' in workspace
    assert 'Capsule Access Grant reconciliation is not admitted yet.' in workspace
    assert (
        "data-principal-types=\"{{ 'service_account' if profile.key.value == 'deployer' else 'user,group' }}\""
        in workspace
    )
    assert 'Filtered by Membership Tenant' in workspace
    assert 'Tenant scope still uses namespaced RBAC' in workspace
    assert 'Select Membership first' in workspace
    assert 'tenant_access_grant_form.js' in page

    assert 'filterTenantOptions' in scope_js
    assert 'option.dataset.tenantId === tenantId' in scope_js
    assert "scopeValue === 'environment'" in scope_js
    assert "scopeValue === 'namespace'" in scope_js
    assert 'environment.required = showEnvironment && Boolean(tenantId)' in scope_js
    assert 'namespace.required = showNamespace && Boolean(tenantId)' in scope_js
    assert 'namespaceCount === 0' in scope_js
    assert "providerKey === 'native_kubernetes'" in scope_js
    assert 'submit.disabled = !enabled' in scope_js
    assert 'Provision Namespace first' in scope_js
    assert 'No target selection is required.' in scope_js
    assert 'incompatible profiles are filtered automatically.' in scope_js
    assert 'normalizedPrincipalType' in scope_js
    assert "window.addEventListener('pageshow'" in scope_js
    assert 'htmx:afterSwap' in scope_js

    # Browser filtering is operator guidance only; server-side Tenant boundary validation remains authoritative.
    assert 'Environment scope cannot cross Tenant boundaries.' in service
    assert 'Namespace scope cannot cross Tenant boundaries.' in service


def test_baseline_capsule_decommission_is_authority_safe_and_residue_gated() -> None:
    service = read('app/kubernetes/tenant/decommission_service.py')
    capsule = read('app/kubernetes/tenant/capsule_tenant.py')
    readme = read('app/kubernetes/tenant/README.md')

    assert 'tenant.ownership_status != TenantOwnershipStatus.MANAGED.value' in service
    assert "provider_evidence.get('created_by_kaori')" in service
    assert "tenant.provider_state != 'capsule'" in service
    assert 'namespace_count' in service
    assert 'access_grant_count or credential_count' in service
    assert 'managed_resource_count' in service
    assert 'delete_capsule_tenant_verified(' in service
    assert "'provider_cleanup': provider_cleanup" in service

    assert 'Capsule Tenant API is unavailable' in capsule
    assert 'Capsule Tenant ownership label does not match committed KAORI Tenant identity.' in capsule
    assert 'Capsule Tenant generation no longer matches committed KAORI intent.' in capsule
    assert 'Capsule Tenant UID changed' in capsule
    assert 'provider absence was not verified before timeout' in capsule

    assert 'baseline Capsule teardown is admitted only' in readme
    assert 'KAORI never falls back to Native deletion' in readme
    assert 'Baseline Capsule decommission:' in readme


def test_tenant_status_guidance_stays_in_block_header_not_table_rows() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    capacity = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    table_standard = read('docs/design/components/TABLE_AND_LABEL.md')
    status_dialog_standard = read('docs/design/components/STATUS_DETAIL_DIALOG.md')

    for template in (registry, discovery, capacity):
        assert 'components/info_tip.html' in template
        assert 'status_detail_dialog' not in template

    assert 'tenant-registry-status-tip' in registry
    assert 'tenant-discovery-status-tip' in discovery
    assert 'allocation-budget-status-tip' in capacity
    assert 'Do not repeat generic' in table_standard
    assert 'outside the table scroll container' in table_standard
    assert 'do **not** use a repeated per-row Status Detail trigger' in status_dialog_standard


def test_governance_flows_use_shared_numbered_sequence_without_arrow_connectors() -> None:
    setup = read('app/templates/kubernetes/tenant/partials/_tenant_setup_workspace.html')
    memberships = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    grants = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    component = read('app/templates/components/numbered_governance_steps.html')

    for template in (setup, memberships, grants):
        assert 'components/numbered_governance_steps.html' in template
        assert 'operational_flow_steps' not in template

    assert '0{{ loop.index }}' in component
    assert "layout='list'" in component
    assert "layout == 'compact-grid'" in component
    assert 'md:grid-cols-2' in component
    assert 'grid-cols-[auto_auto_minmax(0,1fr)]' in component
    assert "layout='compact-grid'" in memberships
    assert "layout='compact-grid'" not in setup
    assert "layout='compact-grid'" not in grants


def test_tenant_registry_blocked_state_uses_shared_header_guidance() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')

    assert 'tenant-registry-status-tip' in registry
    assert 'Lifecycle describes committed Tenant state' in registry
    assert 'Blocked — Tenant stays valid; teardown fails closed until blockers clear.' in registry
    assert "special_label('Blocked', 'critical', 'shield-alert')" in registry
    assert 'tenant-decommission-blocked-' not in registry
    assert 'Current Snapshot' not in registry
    assert 'Governed Flow' not in registry


def test_tenant_discovery_statuses_use_shared_header_guidance() -> None:
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')

    assert 'tenant-discovery-status-tip' in discovery
    assert 'Discovery is live and read-only' in discovery
    assert 'Live Status — current provider observation.' in discovery
    assert 'Discovered — candidate for explicit governed Adoption.' in discovery
    assert 'Provider Missing — KAORI ownership exists but the provider object is absent.' in discovery
    assert 'status_detail_dialog' not in discovery
    assert 'data-status-detail-trigger' not in discovery


def test_tenant_status_rows_do_not_repeat_generic_details_buttons() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    capacity = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')

    for template in (registry, discovery, capacity):
        assert 'status_detail_dialog.trigger' not in template
        assert 'data-status-detail-trigger' not in template


def test_tenant_setup_and_membership_guidance_use_compact_uat_copy() -> None:
    setup = read('app/templates/kubernetes/tenant/partials/_tenant_setup_workspace.html')
    memberships = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')

    assert 'Native Kubernetes and supported Capsule clusters allow direct creation.' in setup
    assert 'Existing Capsule Tenant CRs use Discovery → Adoption.' in setup
    assert 'compatible Capsule clusters support direct Tenant Setup creation' not in setup

    assert 'Revoke disables grants; reactivation does not restore them.' in memberships
    assert 'Reactivation restores membership only; old grants stay revoked.' not in memberships


def test_info_tip_uses_title_level_registry_guidance_and_mobile_top_layer() -> None:
    component = read('app/templates/components/info_tip.html')
    docs = read('docs/design/components/INFO_TIP.md')
    table = read('app/templates/components/table.html')
    table_primitives = read('app/templates/components/table_primitives.html')
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    memberships = read('app/templates/kubernetes/tenant/partials/_membership_registry.html')
    groups = read('app/templates/kubernetes/tenant/partials/_group_registry.html')

    assert 'button_text=None, button_classes=None' in component
    assert 'data-kaori-info-tip' in component
    assert 'data-kaori-info-tip-trigger' in component
    assert 'data-kaori-info-tip-preview' in component
    assert 'sm:group-hover:block' not in component
    assert 'data-kaori-native-dialog' in component
    assert 'data-kaori-dialog-close' in component
    assert 'fixed inset-x-4 bottom-4' not in component

    assert "title_extra=''" in table
    assert '{% if title_extra %}{{ title_extra }}{% endif %}' in table
    assert 'allow_overflow=false' in table_primitives
    assert "'overflow-visible' if allow_overflow else 'overflow-hidden'" in table_primitives

    for template in (registry, discovery, memberships, groups):
        assert 'table_ui.block_classes(allow_overflow=true)' in template
        assert 'title_extra=title_info' in template
        assert "placement='right'" in template

    for retired_text_action in ('Status Guide', 'Membership Guide', 'Group Guide'):
        assert all(f"button_text='{retired_text_action}'" not in template for template in (registry, discovery, memberships, groups))

    layout = read('app/templates/layouts/app.html')
    positioning = read('app/static/js/info_tips.js')
    assert "filename='js/info_tips.js'" in layout
    assert "document.body.appendChild(preview)" in positioning
    assert 'getBoundingClientRect()' in positioning
    assert 'window.innerWidth' in positioning
    assert 'window.innerHeight' in positioning
    assert "document.addEventListener('htmx:beforeSwap'" in positioning

    assert 'beside the registry title' in docs
    assert 'temporarily portals the preview to `document.body`' in docs
    assert 'native `<dialog>` top layer' in docs


def test_credential_issuance_binds_transient_objects_to_tenant_before_validation() -> None:
    human = read('app/kubernetes/tenant/credential_service.py')
    deployer = read('app/kubernetes/tenant/deployer_credential_service.py')

    human_tenant_fk = human.index('credential.tenant_id = grant.tenant_id')
    human_tenant_relationship = human.index('credential.tenant = grant.tenant')
    human_validation = human.index('validate_credential_contract(credential)', human_tenant_relationship)
    assert human_tenant_fk < human_validation
    assert human_tenant_relationship < human_validation

    deployer_membership_fk = deployer.index('membership.tenant_id = tenant.id')
    deployer_grant_fk = deployer.index('grant.tenant_id = tenant.id')
    deployer_credential_fk = deployer.index('credential.tenant_id = tenant.id')
    deployer_grant_validation = deployer.index('validate_active_grant(grant)', deployer_credential_fk)
    deployer_credential_validation = deployer.index(
        'validate_credential_contract(credential)', deployer_grant_validation
    )

    assert deployer_membership_fk < deployer_grant_validation
    assert deployer_grant_fk < deployer_grant_validation
    assert deployer_credential_fk < deployer_credential_validation
    assert 'credential.tenant = tenant' in deployer


def test_credential_material_delivery_is_one_time_non_cached_and_not_routine_inventory() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_credential_registry.html')
    material = read('app/templates/kubernetes/tenant/credential_material.html')
    component = read('app/templates/components/one_time_secret.html')
    routes = read('app/kubernetes/tenant/routes.py')
    service = read('app/kubernetes/tenant/credential_service.py')
    script = read('app/static/js/tenant_credential_material.js')
    clipboard = read('app/static/js/clipboard.js')

    assert 'generate_credential_material_route' in registry
    assert 'data-kaori-sensitive-material' not in registry
    assert 'material_value' not in registry
    assert 'data-kaori-sensitive-material' in component
    assert 'csrf_token_value' in component
    assert 'value="{{ csrf_token_value }}"' in component
    assert 'csrf_token()' not in component
    assert 'csrf_token(),' in registry
    assert 'One-Time Credential Material' in material
    assert 'JumpServer ServiceAccount Token' in material
    assert 'Namespace-Scoped Kubeconfig' in material
    assert 'GitHub Actions Secret (Base64)' in material
    assert 'KAORI does not persist this bearer token or kubeconfig body.' in material

    assert "@tenant_bp.post('/credentials/<int:credential_id>/material')" in routes
    assert "Cache-Control'] = 'no-store, no-cache, must-revalidate, private'" in routes
    assert "Referrer-Policy'] = 'no-referrer'" in routes
    assert "X-Robots-Tag'] = 'noindex, nofollow, noarchive'" in routes
    assert 'generate_credential_material_committed(' in service

    assert 'data-credential-material-namespace' in script
    assert 'data-credential-material-ttl' in script
    assert 'Kubernetes may return a shorter actual expiry.' in script
    assert 'pagehide' in script
    assert 'data-kaori-download-button' in clipboard

def test_legacy_allocation_adoption_is_observed_and_held_until_cutover() -> None:
    observer = read('app/kubernetes/tenant/allocation_observation.py')
    discovery_service = read('app/kubernetes/tenant/discovery_service.py')
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    namespace_registry = read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')
    allocation_change = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    service = read('app/kubernetes/tenant/service.py')
    architecture = read('docs/architecture/kubernetes-tenant-resource-profiles.md')
    readme = read('app/kubernetes/tenant/README.md')

    assert 'observe_native_namespace_allocation' in observer
    assert 'observe_capsule_tenant_allocation' in observer
    assert "'provenance': 'adopted_observed'" in observer
    assert "'provider_mutation_performed': False" in observer
    assert "'control_state': 'control_unavailable'" in observer
    assert 'profile_lineage_for_observed_allocation' in observer
    assert 'GlobalResourceQuota' in observer

    assert 'allocation = observe_native_namespace_allocation' in discovery_service
    assert 'allocation = observe_capsule_tenant_allocation' in discovery_service
    assert "namespace_record.desired_hash = None" in discovery_service
    assert "namespace_record.effective_hash = str(allocation['effective_hash'])" in discovery_service
    assert "'allocation_baseline': allocation" in discovery_service
    assert "TenantOwnershipStatus.ADOPTED.value" in discovery_service

    assert 'Observed Allocation Baseline' in discovery
    assert 'Adopted Baseline · Observed' in discovery
    assert 'Control Unavailable' in discovery
    assert 'Provider authority remains external until an explicit governance cutover is accepted.' in discovery

    assert 'Adopted Baseline · Observed' in namespace_registry
    assert "item.ownership_status == 'adopted'" in namespace_registry
    assert 'Control Unavailable' in namespace_registry
    assert 'Read Only' in namespace_registry

    assert 'namespace_allocation_options' in service
    assert 'record.ownership_status == TenantOwnershipStatus.MANAGED.value' in service
    assert (
        'Adopted Baseline allocations are read-only until explicit '
        'Allocation Governance Cutover is completed.'
    ) in service
    assert 'namespace_allocation_options' in allocation_change
    assert '{% for item in namespace_options %}' not in allocation_change

    assert 'During #768 governed adoption' in architecture
    assert 'governed mutation fails closed' in architecture
    assert 'The resulting Namespace is **Adopted Baseline · Observed**' in readme
    assert 'never turns observed provider state into KAORI-authored desired intent' in readme

def test_adopted_allocation_cutover_is_explicit_provider_verified_and_separate_from_namespace_ownership() -> None:
    cutover = read('app/kubernetes/tenant/allocation_cutover.py')
    service = read('app/kubernetes/tenant/service.py')
    routes = read('app/kubernetes/tenant/routes.py')
    page = read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    cutover_ui = read('app/templates/kubernetes/tenant/partials/_allocation_cutover.html')
    allocation_change = read('app/templates/kubernetes/tenant/partials/_allocation_change.html')
    namespace_registry = read('app/templates/kubernetes/tenant/partials/_namespace_registry.html')

    assert 'def build_allocation_cutover_state' in cutover
    assert 'def reconcile_adopted_native_allocation' in cutover
    assert "record.ownership_status != TenantOwnershipStatus.ADOPTED.value" in cutover
    assert "'allocation_control_state': 'kaori_managed'" in cutover
    assert 'Namespace lifecycle ownership remains adopted.' in cutover
    assert 'resourceVersion changed since observation' in cutover
    assert 'UID changed since observation' in cutover
    assert 'Provider read-back does not match the proposed allocation' in cutover
    assert 'KAORI will not bypass Capsule by writing Native quota directly.' in cutover
    assert 'provider_mutation_may_have_started' in cutover

    assert 'def cutover_adopted_namespace_allocation' in service
    assert 'enforce_existing_namespace_allocation_preflight' in service
    assert "operation='allocation_governance_cutover'" in service
    assert "allocation_control_state(record) != 'kaori_managed'" in service
    assert 'namespace_cutover_options' in service
    assert 'namespace_cutover_state' in service

    assert "@tenant_bp.post('/namespace-allocation/cutover')" in routes
    assert 'cutover_adopted_namespace_allocation_committed' in routes
    assert 'kubernetes_tenant_allocation_cutover_completed' in routes
    assert "'namespace_ownership_status': record.ownership_status" in routes

    assert '_allocation_cutover.html' in page
    assert 'Allocation Governance Cutover' in cutover_ui
    assert 'KAORI Preset · Locked' in cutover_ui
    assert 'Custom · Editable' in cutover_ui
    assert 'Adopted Baseline · Observed' in cutover_ui
    assert 'KAORI Managed' in cutover_ui
    assert 'Cut Over Governance' in cutover_ui
    assert 'Control Unavailable' in cutover_ui
    assert 'Namespace lifecycle ownership stays adopted.' in cutover_ui

    assert 'KAORI-Managed Allocation' in allocation_change
    assert 'Select KAORI-managed allocation' in allocation_change
    assert 'KAORI Managed' in namespace_registry



def test_managed_allocation_drift_is_observation_only_and_bidirectionally_reconciled() -> None:
    drift = read('app/kubernetes/tenant/allocation_drift.py')
    tasks = read('app/kubernetes/tenant/tasks.py')
    routes = read('app/kubernetes/tenant/routes.py')
    registry = read('app/templates/kubernetes/tenant/partials/_operations_drift_registry.html')
    architecture = read('docs/architecture/kubernetes-tenant-resource-profiles.md')
    readme = read('app/kubernetes/tenant/README.md')

    assert 'def apply_managed_allocation_drift_observation' in drift
    assert "'provider_mutation_performed': False" in drift
    assert "'allocation_drift'" in drift
    assert "'differences': differences" in drift
    assert 'def reapply_kaori_allocation_intent' in drift
    assert 'def accept_provider_allocation_state' in drift
    assert 'enforce_observed_namespace_allocation_preflight' in drift
    assert "current_quota_hard=dict(live.get('quota') or {})" in drift
    assert "proposed_quota_hard=record.allocation_quota_json or {}" in drift
    assert "provenance': 'accepted_provider_state'" in drift
    assert 'No admitted reconciliation adapter exists for the current provider authority.' in drift
    assert 'committed Drifted Namespace state' in drift
    assert 'unavailable during teardown' in drift

    assert 'apply_managed_allocation_drift_observation()' in tasks
    assert "snapshot['allocation_drift_count']" in tasks

    assert "@tenant_bp.post('/namespaces/<int:namespace_id>/allocation/reapply')" in routes
    assert "@tenant_bp.post('/namespaces/<int:namespace_id>/allocation/accept-provider-state')" in routes
    assert 'kubernetes_tenant_allocation_reapplied' in routes
    assert 'kubernetes_tenant_allocation_provider_state_accepted' in routes

    assert 'Namespace & Allocation Drift' in registry
    assert 'Reapply KAORI Intent' in registry
    assert 'Accept Provider State' in registry
    assert 'Control Unavailable' in registry
    assert 'difference.kaori_value' in registry
    assert 'difference.provider_value' in registry
    assert "source.get('uid')" in registry
    assert "source.get('resource_version')" in registry

    assert '## Managed allocation drift and bidirectional reconciliation' in architecture
    assert 'current live provider allocation as the current state' in architecture
    assert 'Acceptance performs **no provider write' in architecture
    assert 'Native managed-allocation drift:' in readme
    assert 'Bidirectional allocation recovery:' in readme
    assert '**API**' in readme
    assert '**APE**' in readme
    assert 'Capsule Tenant quota bidirectional recovery:' in readme


def test_capsule_global_resource_quota_joins_canonical_allocation_governance() -> None:
    adoption = read('app/kubernetes/tenant/discovery_service.py')
    qualifier = read('app/kubernetes/tenant/capsule_tenant.py')
    governance = read('app/kubernetes/tenant/capsule_allocation_governance.py')
    advanced = read('app/kubernetes/tenant/capsule_advanced.py')
    capacity = read('app/kubernetes/tenant/capacity_governance.py')
    tasks = read('app/kubernetes/tenant/tasks.py')
    routes = read('app/kubernetes/tenant/routes.py')
    namespace_page = read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    cutover_ui = read('app/templates/kubernetes/tenant/partials/_capsule_shared_allocation_cutover.html')
    operations_page = read('app/templates/kubernetes/tenant/operations.html')
    drift_ui = read('app/templates/kubernetes/tenant/partials/_capsule_shared_allocation_drift.html')
    architecture = read('docs/architecture/kubernetes-tenant-resource-profiles.md')
    capsule_architecture = read('docs/architecture/kubernetes-tenant-capsule-advanced.md')
    readme = read('app/kubernetes/tenant/README.md')

    assert 'qualify_capsule_tenant_adoption' in qualifier
    assert "dry_run='All'" in qualifier
    assert "'adoption_admission_dry_run_verified': admission_verified" in qualifier
    assert 'capsule_capability_evidence' in adoption
    assert "'capsule': capsule_capability_evidence" in adoption
    assert "allocation['control_state'] = 'observed'" in adoption
    assert 'shared_global_quota' in adoption

    assert 'def build_capsule_shared_allocation_cutover_state' in governance
    assert "baseline.get('allocation_authority') != 'capsule_global_resource_quota'" in governance
    assert "_capsule_capability_state(tenant, _SHARED_CAPABILITY) != 'available'" in governance
    assert (
        'An existing Capsule GlobalResourceQuota advanced intent already owns this Tenant resource path.'
        in governance
    )
    assert "intent.resource_kind = 'global_resource_quota'" in governance
    assert "'allocation_governance_scope': _SHARED_SCOPE" in governance
    assert 'enforce_shared_tenant_allocation_preflight' in governance
    assert 'reconcile_capsule_advanced_intent(intent, provider=provider)' in governance
    assert "'provider_mutation_performed': False" in governance
    assert "'provenance': 'accepted_provider_state'" in governance
    assert "'allocation_customized': not _profile_matches_quota(profile, live_quota)" in governance

    assert 'expected_provider_source' in advanced
    assert 'Capsule provider resource UID changed' in advanced
    assert 'Capsule provider resourceVersion changed' in advanced

    assert 'def _canonical_shared_allocation_quota' in capacity
    assert "evidence.get('allocation_governance_scope') != 'tenant_shared'" in capacity
    assert 'def enforce_shared_tenant_allocation_preflight' in capacity
    assert "allocation_scope='tenant_shared'" in capacity
    assert 'shared_quota_by_tenant=shared' in capacity

    assert 'apply_managed_capsule_shared_allocation_drift_observation' in tasks
    assert "snapshot['capsule_shared_allocation_drift_count']" in tasks

    assert "@tenant_bp.post('/shared-allocation/cutover')" in routes
    assert "@tenant_bp.post('/shared-allocation/<int:intent_id>/reapply')" in routes
    assert "@tenant_bp.post('/shared-allocation/<int:intent_id>/accept-provider-state')" in routes
    assert 'CapsuleSharedAllocationStateConflictError' in routes

    assert '_capsule_shared_allocation_cutover.html' in namespace_page
    assert 'Capsule Shared Allocation Governance' in cutover_ui
    assert 'GlobalResourceQuota' in cutover_ui
    assert 'Cut Over Shared Governance' in cutover_ui
    assert 'Control Unavailable' in cutover_ui

    assert '_capsule_shared_allocation_drift.html' in operations_page
    assert 'Capsule Shared Allocation Drift' in drift_ui
    assert 'Reapply KAORI Intent' in drift_ui
    assert 'Accept Provider State' in drift_ui
    assert "source.get('uid')" in drift_ui
    assert "source.get('resource_version')" in drift_ui
    assert 'ops_capsule_shared_page' in routes
    assert 'ops_capsule_shared_per_page' in routes

    assert 'Capsule shared allocation authority' in architecture
    assert 'allocation_governance_scope=tenant_shared' in architecture
    assert 'counted once' in architecture
    assert '#771 does not admit `Tenant.spec.resourceQuotas`; #773 is the separate bounded authority' in architecture
    assert 'Canonical GlobalResourceQuota allocation bridge' in capsule_architecture
    assert 'never copied into every correlated Namespace' in capsule_architecture
    assert 'Capsule GlobalResourceQuota governance:' in readme
    assert 'Legacy Capsule Tenant quota — **estimasi** case:' in readme



def test_capsule_tenant_resource_quotas_are_bidirectionally_governed_without_native_bypass() -> None:
    provider = read('app/kubernetes/tenant/capsule_provider.py')
    observer = read('app/kubernetes/tenant/allocation_observation.py')
    adoption = read('app/kubernetes/tenant/discovery_service.py')
    governance = read('app/kubernetes/tenant/capsule_tenant_quota_governance.py')
    capacity = read('app/kubernetes/tenant/capacity_governance.py')
    tasks = read('app/kubernetes/tenant/tasks.py')
    routes = read('app/kubernetes/tenant/routes.py')
    discovery_ui = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    adoption_preflight_ui = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    namespace_page = read('app/templates/kubernetes/tenant/namespace_provisioning.html')
    cutover_ui = read('app/templates/kubernetes/tenant/partials/_capsule_tenant_quota_cutover.html')
    operations_page = read('app/templates/kubernetes/tenant/operations.html')
    drift_ui = read('app/templates/kubernetes/tenant/partials/_capsule_tenant_quota_drift.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    architecture = read('docs/architecture/kubernetes-tenant-resource-profiles.md')
    readme = read('app/kubernetes/tenant/README.md')

    assert "('spec', 'resourceQuotas')" in provider
    assert "'tenant_resource_quotas': _dependent_status(" in provider
    assert 'def observe_capsule_tenant_resource_quota' in observer
    assert "scope = str(resource_quotas.get('scope') or 'Tenant')" in observer
    assert "'authority_unsupported_dimensions': authority_unsupported" in observer
    assert "'external_constraints': external_constraints" in observer

    assert 'def _apply_capsule_allocation_capability_state' in adoption
    assert "capability = 'tenant_resource_quotas'" in adoption
    assert "allocation['control_state'] = 'observed'" in adoption

    assert 'def build_capsule_tenant_quota_cutover_state' in governance
    assert "baseline.get('allocation_authority') != _AUTHORITY" in governance
    assert "_capsule_capability_state(tenant, _CAPABILITY) != 'available'" in governance
    assert 'def cutover_capsule_tenant_resource_quota' in governance
    assert 'def change_capsule_tenant_resource_quota' in governance
    assert "'spec': {'resourceQuotas':" in governance
    assert "dry_run='All'" in governance
    assert 'Capsule Tenant resourceVersion changed' in governance
    assert 'Capsule Tenant UID changed' in governance
    assert 'def apply_managed_capsule_tenant_quota_drift_observation' in governance
    assert 'def reapply_capsule_tenant_quota_intent' in governance
    assert 'def accept_capsule_tenant_provider_state' in governance
    assert "'provider_mutation_performed': False" in governance
    assert "provenance='accepted_provider_state'" in governance

    assert 'def enforce_capsule_tenant_resource_quota_preflight' in capacity
    assert "normalized_scope = str(scope or 'Tenant')" in capacity
    assert "factor = 1 if normalized_scope == 'Tenant'" in capacity
    assert "'tenant_namespace_template'" in capacity

    assert 'apply_managed_capsule_tenant_quota_drift_observation()' in tasks
    assert "snapshot['capsule_tenant_quota_drift_count']" in tasks

    assert "@tenant_bp.post('/tenant-quota/cutover')" in routes
    assert "@tenant_bp.post('/tenant-quota/change')" in routes
    assert "@tenant_bp.post('/tenant-quota/<string:tenant_id>/reapply')" in routes
    assert "@tenant_bp.post('/tenant-quota/<string:tenant_id>/accept-provider-state')" in routes
    assert 'CapsuleTenantQuotaStateConflictError' in routes
    assert 'ops_capsule_tenant_quota_page' in routes

    assert 'data-tenant-adoption-load' in discovery_ui
    assert 'External Provider Constraints' in adoption_preflight_ui
    assert 'Preserved · Not Rewritten' in adoption_preflight_ui
    assert 'authority_unsupported_dimensions' in adoption_preflight_ui
    assert '_capsule_tenant_quota_cutover.html' in namespace_page
    assert 'tenant-capsule-tenant-quota-state' in namespace_page
    assert 'Capsule Tenant Quota Governance' in cutover_ui
    assert 'Tenant.spec.resourceQuotas' in cutover_ui
    assert 'Take Over Allocation Governance' in cutover_ui
    assert 'Change Governed Allocation' in cutover_ui
    assert 'Native ResourceQuota' in cutover_ui
    assert 'data-tenant-quota-allocation-form' in script
    assert 'data-tenant-quota-managed-form' in script

    assert '_capsule_tenant_quota_drift.html' in operations_page
    assert 'Capsule Tenant Quota Drift' in drift_ui
    assert 'Reapply KAORI Intent' in drift_ui
    assert 'Accept Provider State' in drift_ui
    assert "source.get('uid')" in drift_ui
    assert "source.get('resource_version')" in drift_ui

    assert 'Capsule Tenant resource-quota authority' in architecture
    assert 'Tenant Sync performs no provider write' in architecture
    assert 'Legacy Capsule Tenant quota — **estimasi** case:' in readme
    assert 'Legacy Capsule Tenant quota — **partner** case:' in readme
    assert 'Capsule Tenant quota bidirectional recovery:' in readme
