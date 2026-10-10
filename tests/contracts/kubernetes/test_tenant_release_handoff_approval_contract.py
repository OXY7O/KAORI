from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_release_handoff_plan_is_committed_and_never_claims_provider_transfer():
    service = read('app/kubernetes/tenant/release_handoff_approval.py')
    route = read('app/kubernetes/tenant/routes.py')
    context = read('app/kubernetes/tenant/registry_context.py')
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_management_detail.html')
    handoff = read('app/kubernetes/tenant/release_handoff_inventory.py')

    assert 'def prepare_release_handoff_plan_committed(' in service
    assert 'def approve_release_handoff_plan_committed(' in service
    assert 'review_tenant_release_preflight_committed(' in service
    assert "'kubernetes_tenant_release_handoff_plan'" in service
    assert "'kubernetes_tenant_release_handoff_approval'" in service
    assert 'actor_user_id == plan.get(\'requested_by\')' in service
    assert "'provider_handoff_verified': False" in service
    assert "'release_authorized': False" in service
    assert "'provider_mutation_performed': False" in service
    assert 'if not _checked_recently(plan.get(\'requested_at\'))' in service
    assert "fresh.get('handoff_fingerprint') != plan['handoff_fingerprint']" in service
    assert "existing.get('plan_sha256') == plan_sha256" in service
    assert 'db.session.commit()' in service

    for verb in (
        'patch_namespaced_resource_quota', 'patch_namespaced_limit_range',
        'patch_namespace(', 'create_namespaced_role_binding',
        'delete_namespaced_role_binding', 'delete_namespace(',
        'patch_cluster_custom_object(',
    ):
        assert verb not in service

    assert "@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/prepare')" in route
    assert "@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/approve')" in route
    assert 'def prepare_tenant_release_handoff_route(' in route
    assert 'def approve_tenant_release_handoff_route(' in route
    assert "request.form.get('confirm_handoff_approval') != 'approved'" in route
    assert "plan_sha256=str(request.form.get('plan_sha256') or '')" in route
    assert 'prepare_release_handoff_plan_committed(' in route
    assert 'approve_release_handoff_plan_committed(' in route
    assert route.count("@permission_required('integrations.manage')") >= 3

    assert "'kubernetes_tenant_release_handoff_plan'" in context
    assert "'kubernetes_tenant_release_handoff_approval'" in context
    assert "row['release_handoff_plan']" in context
    assert "row['release_handoff_approval']" in context

    assert 'data-release-handoff-approval' in ui
    assert 'tenant.prepare_tenant_release_handoff_route' in ui
    assert 'tenant.approve_tenant_release_handoff_route' in ui
    assert 'name="successor_owner"' in ui
    assert 'name="change_reference"' in ui
    assert 'name="confirm_handoff_approval"' in ui
    assert 'name="plan_sha256"' in ui
    assert 'handoff_plan.requested_by != current_user.id' in ui
    assert 'External owner acceptance,' in ui

    assert "component['handoff'] = 'external_acceptance_required'" in handoff


def test_canonical_release_executor_remains_blocked_on_managed_allocation():
    release = read('app/kubernetes/tenant/release_preflight.py')
    assert "provider_evidence.get('provider_mutation_performed') is not False" in release
    assert 'row.resource_profile_id is not None' in release
    assert "if latest['status'] != 'handoff_review_required' or latest['blockers']" in release
    assert 'review_tenant_release_preflight_committed(' in release


def test_handoff_preparation_cannot_replace_a_current_approval_request() -> None:
    service = read('app/kubernetes/tenant/release_handoff_approval.py')
    context = read('app/kubernetes/tenant/registry_context.py')
    modal = read('app/templates/kubernetes/tenant/partials/_tenant_management_detail.html')

    assert "def handoff_plan_preparation_state(" in service
    assert "def _require_no_active_handoff_plan(" in service
    lock = service.index("Tenant.query.filter_by(id=tenant_id).with_for_update()")
    check = service.index(
        "_require_no_active_handoff_plan(tenant_id=tenant_id, actor_user_id=actor_user_id)"
    )
    write = service.index("action='tenant.release.handoff_plan_prepared'")
    assert lock < check < write
    assert "state == 'pending'" in service
    assert "state == 'acknowledged'" in service
    assert "state == 'blocked'" in service
    assert "latest_release_handoff_plan(tenant_id)" in service
    assert "latest_release_handoff_approval(tenant_id)" in service

    assert "handoff_plan_preparation_state(" in context
    assert "row['release_handoff_preparation_state']" in context
    assert "row.release_handoff_preparation_state == 'available'" in modal
    assert "handoff_plan.requested_by == current_user.id" in modal
    assert "Only the original requester may renew" in service
    assert "The current handoff plan is locked." in modal
    assert "Acknowledge as Independent Reviewer" in modal
    assert "row.release_handoff_preparation_state == 'pending' and handoff_plan.requested_by != current_user.id" in modal
    assert "External Reference Unverified" in modal
    assert "not an additional approval" in modal
