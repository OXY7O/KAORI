from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_remediation_reuses_existing_governed_plan_for_native_and_capsule():
    plan = read('app/kubernetes/tenant/access_remediation_plan.py')
    analysis = read('app/kubernetes/tenant/access_drift_analysis.py')
    context = read('app/kubernetes/tenant/access_service.py')
    ui = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')

    assert "latest_native_access_drift_evidence" in plan
    assert "latest_tenant_access_drift_evidence" in plan
    assert "'native_kubernetes'" in plan
    assert "'capsule'" in plan
    assert "code == 'active_grant_missing_native_declaration'" in plan
    assert "code == 'active_grant_missing_capsule_declaration'" in plan
    assert "'auto_execute': False" in plan
    assert "'auto_mutation_performed': False" in plan
    assert "'execution_authority': 'existing_access_grant_inspect_reconcile_only'" in plan
    assert "grant.reconciliation_status in {'failed', 'drifted'}" in plan
    assert "evidence.get('effective_rbac_verified') is False" in plan
    assert "evidence.get('cluster_id') != tenant.cluster_id" in plan

    assert 'def latest_native_access_drift_evidence(' in analysis
    assert "'recent_native_access_remediation'" in context
    assert "'recent_capsule_access_remediation'" in context
    assert 'recent_capsule_access_remediation + recent_native_access_remediation' in ui
    assert 'Prepare Native Remediation Decisions' in ui
    assert 'tenant.plan_capsule_access_remediation_route' in ui


def test_remediation_planner_never_mutates_access_provider_automatically():
    plan = read('app/kubernetes/tenant/access_remediation_plan.py')
    for token in (
        'runtime_adapter.build_client', 'patch_namespaced_role_binding(',
        'delete_namespaced_role_binding(', 'reconcile_native_access_grant(',
        'reconcile_capsule_access_grant(', 'create_namespaced_role_binding(',
        'release_adopted_tenant_committed(',
    ):
        assert token not in plan
