from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_native_handoff_dry_run_uses_approved_existing_evidence_and_only_server_dry_run():
    service = read('app/kubernetes/tenant/native_handoff_dry_run.py')
    route = read('app/kubernetes/tenant/routes.py')
    context = read('app/kubernetes/tenant/registry_context.py')
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')

    assert 'def build_native_handoff_patch(' in service
    assert 'def dry_run_native_handoff_component(' in service
    assert 'def dry_run_native_release_handoff_committed(' in service
    assert 'latest_release_handoff_plan(tenant_id)' in service
    assert 'latest_release_handoff_approval(tenant_id)' in service
    assert "_plan_hash(plan) != plan_sha256" in service
    assert 'review_tenant_release_preflight_committed(' in service
    assert '_can_confirm_plan(fresh)' in service
    assert "tenant.provider_key != 'native_kubernetes'" in service
    assert "tenant.reconciliation_authority != 'native_kubernetes'" in service
    assert "if len(components) > _MAX_COMPONENTS:" in service
    assert "'dry_run': 'All'" in service
    assert "_CONTENT_TYPE = 'application/json-patch+json'" in service
    assert "if _spec(before) != _spec(preview)" in service
    assert "if _resource_metadata(live) != before_identity" in service
    assert "'provider_mutation_performed': False" in service
    assert "'provider_handoff_verified': False" in service
    assert "'release_authorized': False" in service
    assert "'dry_run_only': True" in service
    assert "db.session.commit()" in service
    assert "def release_adopted_tenant_committed" not in service

    assert "@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/native-dry-run')" in route
    assert "@permission_required('integrations.manage')" in route
    assert "request.form.get('confirm_native_handoff_dry_run') != 'approved'" in route
    assert 'dry_run_native_release_handoff_committed(' in route

    assert "'kubernetes_tenant_release_native_handoff_dry_run'" in context
    assert "row['release_native_handoff_dry_run']" in context
    assert 'tenant.dry_run_native_release_handoff_route' in ui
    assert 'name="confirm_native_handoff_dry_run"' in ui
    assert 'Preview Native Transfer' in ui
    assert 'Provider mutation: none. Release is still blocked.' in ui


def test_native_preview_never_reuses_destructive_allocation_reconcile_or_provider_cleanup():
    service = read('app/kubernetes/tenant/native_handoff_dry_run.py')
    for token in (
        'delete_namespace(', 'delete_namespaced_resource_quota(',
        'delete_namespaced_limit_range(', 'replace_namespaced_resource_quota(',
        'delete_namespaced_role_binding(', 'reconcile_adopted_native_allocation(',
        'release_adopted_tenant_committed(',
    ):
        assert token not in service
    assert "'op': 'remove'" in service
    assert "'op': 'test'" in service
    assert "'dry_run': 'All'" in service
    assert "spec_unchanged" in service
    assert "live_provider_unchanged" in service
