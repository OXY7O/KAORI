from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_native_access_drift_reuses_committed_observation_and_canonical_workspace():
    service = read('app/kubernetes/tenant/access_drift_analysis.py')
    routes = read('app/kubernetes/tenant/routes_access.py')
    context = read('app/kubernetes/tenant/access_service.py')
    ui = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')

    assert 'def classify_native_access_observation(' in service
    assert 'def evaluate_native_access_drift_committed(' in service
    assert 'latest_external_native_access_evidence(tenant_id)' in service
    assert "'kubernetes_tenant_native_access_drift_evidence'" in service
    assert "TenantAccessGrant.query.filter_by(tenant_id=tenant_id).all()" in service
    assert "observed_at" in service
    assert "changed > timestamp" in service
    assert "'effective_rbac_verified': False" in service
    assert "'auto_remediation_performed': False" in service
    assert "'native_grant_scope_mismatch'" in service
    assert "'native_grant_role_reference_mismatch'" in service
    assert "'unverified_kaori_grant_marker'" in service
    assert 'runtime_adapter.build_client' not in service
    assert 'patch_namespaced_role_binding' not in service
    assert 'reconcile_provider_access_grant(' not in service

    assert "@tenant_bp.post('/external-access/analyze-native')" in routes
    assert '@permission_required(\'tenant.manage\')' in routes
    assert 'evaluate_native_access_drift_committed(' in routes
    assert '_csrf()' in routes
    assert "'recent_native_access_drift'" in context
    assert 'tenant.analyze_native_access_drift_route' in ui
    assert 'Analyze Native Access Drift' in ui
    assert 'Native Access Drift · committed findings' in ui
    assert 'No automatic remediation was performed.' in ui
