from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


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
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
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
    assert 'reconcile_native_access_grant(grant)' in service
    assert "action='tenant_access_grant.membership_revoked'" in service
    assert 'one or more Kubernetes RoleBindings require operator attention' in service


def test_revoked_membership_reactivation_preserves_grant_history_and_fails_closed() -> None:
    service = read('app/kubernetes/tenant/access_service.py')
    routes = read('app/kubernetes/tenant/routes.py')
    registry = read('app/templates/kubernetes/tenant/partials/_membership_registry.html')
    grant_registry = read('app/templates/kubernetes/tenant/partials/_access_grant_registry.html')
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
    assert "grant.status == 'active' or grant.reconciliation_status != 'revoked'" in grant_registry
    assert "url_for('tenant.reconcile_access_grant_route', grant_id=grant.id)" in grant_registry
    assert 'old grants stay revoked' in workspace

    assert 'Previous Access Grants remain revoked permanently' in docs
    assert 'new Access Grant' in docs


def test_tenant_group_edit_retire_and_reactivate_preserve_identity_history() -> None:
    service = read('app/kubernetes/tenant/access_service.py')
    routes = read('app/kubernetes/tenant/routes.py')
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
    assert 'No external IdP group is deleted.' in registry
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
    service = read('app/kubernetes/tenant/access_service.py')

    assert "profile_order = ('viewer', 'operator', 'tenant_admin', 'deployer')" in service


def test_apply_access_grant_form_uses_context_preview_instead_of_redundant_helper_copy() -> None:
    workspace = read('app/templates/kubernetes/tenant/partials/_tenant_access_grants_workspace.html')
    script = read('app/static/js/tenant_access_grant_form.js')

    assert 'Apply Access Grant' in workspace
    assert 'access-membership-tip' in workspace
    assert 'access-profile-tip' in workspace
    assert 'access-scope-tip' in workspace
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
    assert 'provider mutation remains blocked.' in script
    assert 'data-access-profile-guidance' not in script
    assert 'data-access-scope-guidance' not in script
