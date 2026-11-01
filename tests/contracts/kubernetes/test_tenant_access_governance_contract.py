from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def read_routes() -> str:
    return '\n'.join(
        read(path)
        for path in (
            'app/kubernetes/tenant/routes.py',
            'app/kubernetes/tenant/route_common.py',
            'app/kubernetes/tenant/routes_access.py',
            'app/kubernetes/tenant/routes_credentials.py',
        )
    )


def test_tenant_access_governance_keeps_application_and_kubernetes_rbac_separate() -> None:
    model_source = (ROOT / 'app/models/tenant.py').read_text(encoding='utf-8')
    access_source = (ROOT / 'app/kubernetes/tenant/access.py').read_text(encoding='utf-8')
    reconciliation_source = (ROOT / 'app/kubernetes/tenant/access_reconciliation.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260926_tenant_access_grants.py').read_text(encoding='utf-8')
    architecture = (ROOT / 'docs/architecture/kubernetes-tenant-access-governance.md').read_text(encoding='utf-8')
    rbac_architecture = (ROOT / 'docs/rbac/RBAC_ARCHITECTURE.md').read_text(encoding='utf-8')

    for model in ('TenantGroup', 'TenantMembership', 'TenantAccessGrant'):
        assert f'class {model}(db.Model):' in model_source

    for profile in ("'viewer'", "'operator'", "'tenant_admin'", "'deployer'"):
        assert profile in access_source

    assert 'ClusterRoleBinding' not in reconciliation_source
    assert 'RbacAuthorizationV1Api' in (
        ROOT / 'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/client.py'
    ).read_text(encoding='utf-8')
    assert "down_revision = '20260925_tenant_capacity'" in migration
    assert 'KAORI application RBAC and Tenant Kubernetes RBAC are separate authorization layers.' in architecture
    assert 'They do not extend `User.has_permission()`' in rbac_architecture


def test_tenant_access_profiles_forbid_wildcard_and_platform_scope() -> None:
    access_source = (ROOT / 'app/kubernetes/tenant/access.py').read_text(encoding='utf-8')
    assert "'clusterrolebindings'" in access_source
    assert "'clusterroles'" in access_source
    assert "'namespaces'" in access_source
    assert "'resourcequotas'" in access_source
    assert "'rolebindings'" in access_source
    assert "'roles'" in access_source
    assert "if '*' in rule.api_groups or '*' in rule.verbs" in access_source


def test_tenant_access_revocation_records_effective_removal_evidence() -> None:
    service_source = (ROOT / 'app/kubernetes/tenant/access_service.py').read_text(encoding='utf-8')
    reconciliation_source = (ROOT / 'app/kubernetes/tenant/access_reconciliation.py').read_text(encoding='utf-8')
    assert 'tenant_access_grant.revoked' in service_source
    assert 'provider access removal requires attention' in service_source
    assert '_delete_binding(api, grant, namespace)' in reconciliation_source
    assert 'Revoked Tenant Access Grant still has effective RoleBinding state.' in reconciliation_source


def test_tenant_members_access_uat_surface_uses_canonical_access_services() -> None:
    routes = read_routes()
    service = (ROOT / 'app/kubernetes/tenant/access_service.py').read_text(encoding='utf-8')
    template = ''.join(
        [
            (ROOT / 'app/templates/kubernetes/tenant/tenants.html').read_text(encoding='utf-8'),
            (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html').read_text(
                encoding='utf-8'
            ),
            (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html').read_text(
                encoding='utf-8'
            ),
            (ROOT / 'app/templates/kubernetes/tenant/partials/_membership_registry.html').read_text(encoding='utf-8'),
            (ROOT / 'app/templates/kubernetes/tenant/partials/_access_grant_registry.html').read_text(encoding='utf-8'),
            read('app/templates/kubernetes/tenant/partials/_access_grant_row_detail.html'),
        ]
    )

    for route in (
        "@tenant_bp.post('/groups')",
        "@tenant_bp.post('/groups/<int:group_id>/edit')",
        "@tenant_bp.post('/groups/<int:group_id>/retire')",
        "@tenant_bp.post('/groups/<int:group_id>/reactivate')",
        "@tenant_bp.post('/memberships/users')",
        "@tenant_bp.post('/memberships/groups')",
        "@tenant_bp.post('/memberships/<int:membership_id>/revoke')",
        "@tenant_bp.post('/access-grants')",
        "@tenant_bp.post('/access-grants/<int:grant_id>/inspect')",
        "@tenant_bp.post('/access-grants/<int:grant_id>/reconcile')",
        "@tenant_bp.post('/access-grants/<int:grant_id>/revoke')",
    ):
        assert route in routes

    for mutation in (
        'create_tenant_group_by_id_committed',
        'update_tenant_group_by_id_committed',
        'retire_tenant_group_by_id_committed',
        'reactivate_tenant_group_by_id_committed',
        'add_user_membership_by_id_committed',
        'add_group_membership_by_id_committed',
        'create_access_grant_by_id_committed',
        'inspect_access_grant_by_id_committed',
        'reconcile_access_grant_by_id_committed',
        'revoke_access_grant_by_id_committed',
        'revoke_membership_by_id_committed',
    ):
        assert mutation in routes

    assert 'from app.extensions.db import db' not in routes
    assert 'db.session' not in routes
    assert 'Add User Membership' in template
    assert 'Tenant Group' in template
    assert 'Functional UAT Surface' not in template
    assert 'Apply Access Grant' in template
    assert 'Inspect' in template
    assert 'Reconcile' in template
    assert 'Revoke' in template
    assert 'get_tenant_access_context' in service


def test_membership_revocation_is_fail_closed_for_dependent_grants() -> None:
    service = (ROOT / 'app/kubernetes/tenant/access_service.py').read_text(encoding='utf-8')

    assert 'membership.status = TenantMembershipStatus.REVOKED.value' in service
    assert 'grant.status = TenantAccessGrantStatus.REVOKED.value' in service
    assert 'reconcile_provider_access_grant(grant)' in service
    dispatcher = read('app/kubernetes/tenant/access_provider.py')
    assert 'reconcile_native_access_grant(grant)' in dispatcher
    assert 'reconcile_capsule_access_grant(grant)' in dispatcher
    assert "action='tenant_access_grant.membership_revoked'" in service
    assert 'one or more Kubernetes RoleBindings require operator attention' in service


def test_revoked_membership_reactivation_preserves_grant_history_and_fails_closed() -> None:
    service = read('app/kubernetes/tenant/access_service.py')
    routes = read_routes()
    registry = read('app/templates/kubernetes/tenant/partials/_membership_registry.html')
    grant_registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    grant_detail = read('app/templates/kubernetes/tenant/partials/_access_grant_row_detail.html')
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    docs = read('docs/architecture/kubernetes-tenant-access-governance.md')

    assert 'def reactivate_membership_committed(*, membership_id: int' in service
    assert 'TenantMembershipStatus.ACTIVE.value' in service
    assert 'grant.reconciliation_status != TenantAccessReconciliationStatus.REVOKED.value' in service
    assert 'previous Access Grants remain revoked' in service
    assert 'Membership reactivation currently supports User and Tenant Group principals only.' in service
    assert 'Reactivate it from the Membership Registry.' in service

    assert "@tenant_bp.post('/memberships/<int:membership_id>/reactivate')" in routes
    assert 'reactivate_membership_by_id_committed' in routes
    assert "operation': 'reactivate_membership'" in routes
    assert 'Previous Access Grants remain revoked.' in routes
    assert 'Apply a new Access Grant when access should be restored.' in routes

    assert "url_for('tenant.reactivate_membership_route', membership_id=membership.id)" in registry
    assert 'Reactivate' in registry
    assert '_access_grant_row_detail.html' in grant_registry
    assert "grant.status == 'active' or grant.reconciliation_status != 'revoked'" in grant_detail
    assert "url_for('tenant.reconcile_access_grant_route', grant_id=grant.id)" in grant_detail
    assert "url_for('tenant.revoke_access_grant_route', grant_id=grant.id)" in grant_detail
    assert 'name="csrf_token" value="{{ csrf_token() }}"' in grant_detail
    assert 'Reactivation does not restore old grants.' in workspace

    assert 'Previous Access Grants remain revoked permanently' in docs
    assert 'new Access Grant' in docs


def test_tenant_group_edit_retire_and_reactivate_preserve_identity_history() -> None:
    service = read('app/kubernetes/tenant/access_service.py')
    routes = read_routes()
    registry = read('app/templates/kubernetes/tenant/partials/_group_registry.html')
    modal_js = read('app/static/js/tenant_group_modal.js')
    architecture = read('docs/architecture/kubernetes-tenant-access-governance.md')

    assert 'def update_tenant_group_committed(' in service
    assert 'group.slug' in service
    assert 'membership.subject_name = subject' in service
    assert 'reconcile_access_grant_committed(grant_id=int(grant.id), actor=actor)' in service
    assert 'def retire_tenant_group_committed(' in service
    assert 'Revoke the active Tenant Group membership before retiring this group.' in service
    assert 'def reactivate_tenant_group_committed(' in service
    assert "action='tenant_group.retired'" in service
    assert "action='tenant_group.reactivated'" in service

    assert "@tenant_bp.post('/groups/<int:group_id>/edit')" in routes
    assert "@tenant_bp.post('/groups/<int:group_id>/retire')" in routes
    assert "@tenant_bp.post('/groups/<int:group_id>/reactivate')" in routes
    assert '/groups/<int:group_id>/delete' not in routes

    assert 'Edit Tenant Group' in registry
    assert 'Retire' in registry
    assert 'Reactivate' in registry
    assert 'data-tenant-group-edit-open' in registry
    assert 'tenant-group-retire-modal' in registry
    assert 'KAORI does not modify or delete the authoritative external group.' in registry
    assert 'Retire requires revoked Memberships and reconciled grants.' in registry
    assert 'Revoked memberships, access grants, correlation, and audit evidence remain queryable.' in registry
    assert 'data-tenant-group-edit-modal' in modal_js
    assert 'htmx:afterRequest' in modal_js

    assert 'Routine Tenant UI does not hard-delete Tenant Group records' in architecture
    assert 'stable KAORI identity key' in architecture


def test_namespace_provisioning_reconciles_matching_broad_scope_grants_after_commit() -> None:
    access_service = read('app/kubernetes/tenant/access_service.py')
    tenant_service = read('app/kubernetes/tenant/service.py')
    sync_service = read('app/kubernetes/tenant/sync_service.py')
    architecture = read('docs/architecture/kubernetes-tenant-access-governance.md')

    assert 'def reconcile_access_grants_for_namespace_committed(' in access_service
    assert 'TenantAccessScope.TENANT.value' in access_service
    assert 'TenantAccessScope.ENVIRONMENT.value' in access_service
    assert 'TenantAccessGrant.tenant_environment_id == namespace.tenant_environment_id' in access_service
    assert "action='tenant_access_grant.namespace_scope_expanded'" in access_service
    assert "action='tenant_access_grant.namespace_scope_expand_failed'" in access_service
    assert "return {'matched': len(grants), 'reconciled': reconciled, 'failed': failed}" in access_service

    provision_start = tenant_service.index('def provision_native_namespace(')
    provision_end = tenant_service.index('def change_native_namespace_allocation(')
    provision = tenant_service[provision_start:provision_end]
    assert provision.index('db.session.commit()') < provision.index(
        'reconcile_access_grants_for_namespace_committed(namespace=record)'
    )
    assert (
        'from app.kubernetes.tenant.access_service import reconcile_access_grants_for_namespace_committed' in provision
    )
    assert "evidence['access_grant_followup']" in provision
    assert "'trigger': 'explicit_namespace_provision'" in provision
    assert 'Access Grant follow-up:' in provision

    assert 'reconcile_access_grants_for_namespace_committed' not in sync_service
    assert 'sync remains observation-only' in architecture
    assert 'never infer Namespace scope automatically' in architecture


def test_access_profiles_render_in_least_privilege_operator_order() -> None:
    workspace = read('app/kubernetes/tenant/admin_workspace.py')

    assert "profile_order = ('viewer', 'operator', 'tenant_admin', 'deployer')" in workspace
    assert 'ACCESS_PROFILE_CATALOG[(key, LATEST_ACCESS_PROFILE_VERSION[key])]' in workspace
    assert 'for key in profile_order' in workspace
    assert 'if key in LATEST_ACCESS_PROFILE_VERSION' in workspace
    assert "'access_profiles': profiles" in workspace


def test_apply_access_grant_form_uses_context_preview_instead_of_redundant_helper_copy() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    script = read('app/static/js/tenant_access_grant_form.js')

    assert 'Apply Access Grant' in workspace
    # The accepted Grant Context preview replaces the former three inline tooltips.
    for field_id, label in (
        ('access-grant-membership', 'Membership'),
        ('access-grant-profile', 'Access Profile'),
        ('access-grant-scope', 'Scope'),
    ):
        assert f'for="{field_id}"' in workspace
        assert f'>{label}</label>' in workspace
    for removed_tip in ('access-membership-tip', 'access-profile-tip', 'access-scope-tip'):
        assert removed_tip not in workspace
    assert 'data-access-profile-guidance' not in workspace
    assert 'data-access-scope-guidance' not in workspace
    assert 'Select Membership first; incompatible profiles are filtered automatically.' not in workspace
    assert 'Tenant and scope are validated before commit.' not in workspace

    assert 'data-access-grant-context' in workspace
    assert 'Grant Context' in workspace
    assert 'Live preview of the authorization intent before commit.' in workspace
    assert 'data-access-context-principal' in workspace
    assert 'data-access-context-tenant' in workspace
    assert 'data-access-context-profile' in workspace
    assert 'data-access-context-scope' in workspace
    assert 'data-access-context-provider' in workspace
    assert 'flex min-h-[14rem] flex-1 flex-col' in workspace
    assert 'sm:grid-cols-2' in workspace
    assert 'Filtered by Membership Tenant' in workspace

    assert 'const syncContext = (' in script
    assert 'membershipOption?.dataset.subjectName' in script
    assert "target.matches('[data-access-environment]')" in script
    assert "target.matches('[data-access-namespace]')" in script
    assert 'Native Kubernetes authority selected.' in script
    assert 'Unsupported mutation remains blocked.' in script
    assert 'data-provider-state' in workspace
    assert 'data-reconciliation-authority' in workspace
    assert 'data-access-profile-guidance' not in script
    assert 'data-access-scope-guidance' not in script


def test_access_grant_registry_reconciliation_uses_canonical_expandable_evidence() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    detail = read('app/templates/kubernetes/tenant/partials/_access_grant_row_detail.html')
    shared = read('app/templates/components/details/_expandable_row.html')

    # Reconciliation remains visible in the registry even before detail expansion.
    assert 'table_label.status_label(grant.reconciliation_status|title, reconciliation_tone)' in registry
    assert 'aria-label="Access Grant actions"' in registry
    assert "url_for('tenant.inspect_access_grant_route', grant_id=grant.id)" in registry
    assert 'name="csrf_token"' in registry

    # Use the existing accessible, static expandable table row, not a legacy tooltip.
    assert '{% import "components/details/_expandable_row.html" as detail_row %}' in registry
    assert "detail_row.toggle_button('tenant-access-grants'" in registry
    assert 'detail_row.static_detail_row(detail_row_id, detail_target_id, 6' in registry
    assert "{% include 'kubernetes/tenant/partials/_access_grant_row_detail.html' %}" in registry
    assert 'data-detail-toggle' in shared
    assert 'aria-controls="{{ row_id }}"' in shared
    assert 'aria-expanded="false"' in shared
    assert 'data-detail-static="true"' in shared

    # The expanded evidence preserves the principal/tenant/profile/scope and fail-closed actions.
    assert 'data-access-grant-expanded-evidence' in detail
    assert 'aria-label="Access Grant expanded details"' in detail
    assert 'aria-label="Selected Access Grant"' in detail
    assert 'Provider Reconciliation' in detail
    assert 'table_label.status_label(grant.reconciliation_status|title, reconciliation_tone)' in detail
    for label in ('Principal', 'Tenant', 'Profile', 'Scope'):
        assert f'>{label}</dt>' in detail
    assert "if can_manage and (grant.status == 'active' or grant.reconciliation_status != 'revoked')" in detail
    assert "url_for('tenant.reconcile_access_grant_route', grant_id=grant.id)" in detail
    assert "url_for('tenant.revoke_access_grant_route', grant_id=grant.id)" in detail
    assert 'name="csrf_token"' in detail


def test_grant_context_exposes_canonical_capsule_role_preparation_modal_without_provider_mutation() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    modal = read('app/templates/kubernetes/tenant/partials/_capsule_access_role_manifest_dialog.html')
    workspace_owner = read('app/kubernetes/tenant/admin_workspace.py')
    access = read('app/kubernetes/tenant/access.py')
    reconciliation = read('app/kubernetes/tenant/capsule_access_reconciliation.py')
    native_dialogs = read('app/static/js/native_dialogs.js')
    clipboard = read('app/static/js/clipboard.js')

    assert 'data-access-grant-context' in workspace
    assert 'Capsule RBAC Prerequisites' in workspace
    assert 'Prepare Roles' in workspace
    assert 'data-kaori-dialog-open' in workspace
    assert 'data-dialog-target="capsule-access-role-manifest-dialog"' in workspace
    assert '{% include "kubernetes/tenant/partials/_capsule_access_role_manifest_dialog.html" %}' in workspace
    assert 'data-kaori-native-dialog' in modal
    assert 'aria-labelledby="capsule-access-role-manifest-title"' in modal
    assert 'data-kaori-dialog-close' in modal
    assert 'access_capsule_role_manifests' in modal
    assert 'access_capsule_role_bundle_yaml' in modal
    assert 'data-kaori-copy-button' in modal
    assert 'data-kaori-download-button' in modal
    assert 'data-kaori-copy-source' in modal
    assert 'kubectl apply -f kaori-capsule-access-clusterroles.yaml' in modal
    assert 'No Kubernetes mutation has occurred.' in modal
    assert 'data-kaori-dialog-open' in native_dialogs
    assert 'data-kaori-copy-root' in clipboard
    assert 'data-kaori-download-button' in clipboard
    assert 'capsule_cluster_role_manifest(profile)' in workspace_owner
    assert 'yaml.safe_dump_all(' in workspace_owner
    assert 'def capsule_cluster_role_manifest(' in access
    assert 'capsule_cluster_role_name(profile)' in reconciliation
    assert 'create_cluster_role(' not in modal
    assert 'ClusterRoleBinding' not in modal


def test_access_grant_registry_shortcut_scrolls_nested_main_to_complete_form() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    form = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    script = read('app/static/js/tenant_access_grant_form.js')
    shell = read('app/templates/layouts/app.html')

    assert 'data-access-grant-form-shortcut' in registry
    assert 'Go to Grant Form' in registry
    assert 'aria-controls="access-grant-form"' in registry
    assert "'#access-grant-form'" not in registry
    assert "'Apply Grant'," not in registry
    assert 'id="access-grant-form"' in form
    assert 'data-access-submit' in form
    assert 'data-kaori-main-scroll' in shell
    assert "form.closest('[data-kaori-main-scroll]')" in script
    assert 'scrollHost.scrollTop' in script
    assert 'form.getBoundingClientRect().top' in script
    assert 'scrollHost.getBoundingClientRect().top' in script
    assert "scrollHost.scrollTo({ top: Math.max(0, destination), behavior: 'auto' })" in script
    assert "document.addEventListener('click'" in script
    assert "target?.closest('[data-access-grant-form-shortcut]')" in script
    assert 'event.preventDefault()' in script
    assert "form.querySelector('[data-access-membership]')" in script
    assert 'membership.focus({ preventScroll: true })' in script


def test_access_grants_included_provider_evidence_templates_compile_and_render() -> None:
    """#1211: both read-only provider tabs must render without an HTTP 500."""
    from types import SimpleNamespace

    from jinja2 import Environment, FileSystemLoader

    templates = ROOT / 'app/templates'
    environment = Environment(loader=FileSystemLoader(str(templates)), autoescape=True)

    # The bare Jinja test harness registers the same filter names the app does.
    # No provider or database access is needed to render the empty committed state.
    def environment_name(value: object, empty: str = 'Environment not specified') -> str:
        return str(value) if value else empty

    def url_for(_endpoint: str, **_params: object) -> str:
        return '/test/tenant/access'

    def csrf_token() -> str:
        return 'test-csrf'

    environment.filters['environment_name'] = environment_name
    environment.filters['user_datetime'] = str
    environment.globals['url_for'] = url_for
    environment.globals['csrf_token'] = csrf_token
    environment.globals['request'] = SimpleNamespace(view_args={})
    for name in (
        'kubernetes/tenant/partials/_tenant_admin_workspace.html',
        'kubernetes/tenant/partials/_tenant_access_grants_workspace.html',
        'kubernetes/tenant/partials/_access_inventory_workspace.html',
        'kubernetes/tenant/partials/_external_capsule_access_inventory.html',
        'kubernetes/tenant/partials/_native_namespace_rbac_inventory.html',
    ):
        environment.get_template(name)

    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_admin_workspace.html')
    grants = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    inventory = read('app/templates/kubernetes/tenant/partials/_access_inventory_workspace.html')
    assert "('access-grants', 'Access Grants'" in workspace
    assert "hx_target='#tenant-admin-workspace'" in workspace
    assert "hx_select='#tenant-admin-workspace'" in workspace
    assert '_tenant_access_grants_workspace.html' in workspace
    assert '_access_inventory_workspace.html' in grants
    assert 'workspace_tabs.render_query_tabs(' in inventory
    assert "active_access_inventory_view == 'grants'" in inventory
    assert '_access_grant_registry.html' in inventory
    assert '_external_capsule_access_inventory.html' in inventory
    assert '_native_namespace_rbac_inventory.html' in inventory

    pagination = SimpleNamespace(
        total_items=0,
        start_item=0,
        end_item=0,
        page=1,
        total_pages=1,
        per_page=5,
        allowed_per_page=(5, 10, 25),
        prev_page=1,
        next_page=1,
        has_prev=False,
        has_next=False,
    )
    baseline = {
        'can_manage': False,
        'external_capsule_tenants': [],
        'recent_external_capsule_access': [],
        'external_native_tenants': [],
        'recent_external_native_access': [],
        'recent_external_access_profile_reviews': [],
        'access_evidence_total': 0,
        'access_evidence_review_required': 0,
        'access_evidence_filters': SimpleNamespace(search='', status=''),
        'access_evidence_pagination': pagination,
        'access_evidence_rows': [],
        'access_evidence_drift_by_tenant': {},
        'access_evidence_remediation_by_observation': {},
    }

    capsule = environment.get_template('kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    rendered_capsule = capsule.render(**baseline)
    assert 'External Capsule Access Inventory' in rendered_capsule
    assert 'Capsule remains authoritative.' in rendered_capsule
    assert 'No committed external-access inspection yet.' in rendered_capsule
    assert 'data-kaori-canonical-registry-footer="tenant-capsule-evidence-registry"' in rendered_capsule

    native = environment.get_template('kubernetes/tenant/partials/_native_namespace_rbac_inventory.html')
    rendered_native = native.render(**baseline)
    assert 'Native Namespace RBAC Inventory' in rendered_native
    assert 'No committed Native RBAC observation yet.' in rendered_native
    assert 'Inspection does not mutate membership, identity or RBAC.' in rendered_native
    assert 'data-kaori-canonical-registry-footer="tenant-native-evidence-registry"' in rendered_native

    for rendered in (rendered_capsule, rendered_native):
        assert 'data-tenant-provider-evidence-loading' in rendered
        assert 'data-kaori-canonical-registry-filter' in rendered
        assert 'name="csrf_token"' not in rendered

    evidence_rows = read('app/templates/kubernetes/tenant/partials/_provider_access_evidence_rows.html')
    assert '{% set evidence = event.metadata_json or {} %}' in evidence_rows
    assert '_provider_access_evidence_detail.html' in evidence_rows


def test_access_grant_registry_actions_fit_desktop_and_use_accessible_expanded_detail() -> None:
    """#1215: no clipped actions or mutation controls inside a scrolling table."""
    from jinja2 import Environment

    registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
    detail = read('app/templates/kubernetes/tenant/partials/_access_grant_row_detail.html')
    shared = read('app/templates/components/details/_expandable_row.html')
    credentials = read('app/templates/kubernetes/tenant/partials/_credential_registry.html')
    credential_detail = read('app/templates/kubernetes/tenant/partials/_credential_row_detail.html')
    Environment(autoescape=True).parse(registry)
    Environment(autoescape=True).parse(detail)

    assert "table_ui.table_classes('min-w-[1040px] table-fixed xl:min-w-0')" in registry
    assert 'overflow-x-auto xl:overflow-visible' in registry
    assert "table_ui.table_classes('min-w-[1300px] !table-fixed')" not in registry
    assert 'w-[20%]">Actions' in registry
    assert 'min-w-[15rem] flex-wrap' not in registry
    assert 'flex items-center justify-end gap-1.5 whitespace-nowrap' in registry
    assert 'aria-label="Access Grant actions"' in registry
    assert "detail_row.toggle_button('tenant-access-grants'" in registry
    assert 'detail_row.static_detail_row(detail_row_id, detail_target_id, 6' in registry
    assert "{% include 'kubernetes/tenant/partials/_access_grant_row_detail.html' %}" in registry
    assert 'aria-expanded="false"' in shared
    assert 'aria-controls="{{ row_id }}"' in shared
    assert 'data-detail-static="true"' in shared
    assert 'aria-label="Access Grant expanded details"' in detail

    # Both registries use the shared accessible detail row; credential material
    # generation retains its separate governed one-time request dialog.
    assert "detail_row.toggle_button('tenant-credentials'" in credentials
    assert 'detail_row.static_detail_row(detail_row_id, detail_target_id, 6' in credentials
    assert '_credential_row_detail.html' in credentials
    assert 'aria-label="Credential expanded details"' in credential_detail
    assert 'data-dialog-target="credential-material-request-{{ credential.id }}"' in credential_detail
    assert 'data-kaori-native-dialog' not in registry

    viewport_end = registry.index('</table>')
    footer_end = registry.index('registry_ui.footer(', viewport_end)
    assert viewport_end < footer_end
    assert registry.index('inspect_access_grant_route') < viewport_end
    assert 'reconcile_access_grant_route' not in registry
    assert 'revoke_access_grant_route' not in registry
    assert "if can_manage and (grant.status == 'active' or grant.reconciliation_status != 'revoked')" in detail
    assert "if grant.status == 'active'" in detail
    for route in ('reconcile_access_grant_route', 'revoke_access_grant_route'):
        endpoint = f'tenant.{route}'
        assert detail.count(f'action="{{{{ url_for(\'{endpoint}\', grant_id=grant.id) }}}}"') == 1
        assert detail.count(f'hx-post="{{{{ url_for(\'{endpoint}\', grant_id=grant.id) }}}}"') == 1
    assert registry.count('name="csrf_token"') == 1
    assert detail.count('name="csrf_token"') == 2
    assert detail.count('hx-target="#tenant-admin-workspace"') == 2
    assert detail.count('hx-select="#tenant-admin-workspace"') == 2
    assert detail.count('hx-disabled-elt="find button"') == 2
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.footer' in registry
    assert 'access_grant_pagination.allowed_per_page' in registry
    assert "action_button.classes('critical')" in detail
