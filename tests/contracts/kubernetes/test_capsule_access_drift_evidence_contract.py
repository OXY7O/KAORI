from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_external_capsule_access_drift_uses_committed_evidence_not_live_reconcile():
    service = read('app/kubernetes/tenant/access_drift_analysis.py')
    route = read('app/kubernetes/tenant/routes_access.py')
    context = read('app/kubernetes/tenant/access_service.py')
    template = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')

    assert 'latest_external_capsule_access_evidence(tenant_id)' in service
    assert 'TenantAccessGrant.query.filter_by(tenant_id=tenant_id).all()' in service
    assert "'auto_remediation_performed': False" in service
    assert "'effective_rbac_verified': False" in service
    assert 'db.session.add(AuditEvent(' in service
    assert 'runtime_adapter.build_client' not in service
    assert 'patch_cluster_custom_object' not in service
    assert 'reconcile_provider_access_grant(' not in service

    assert "@tenant_bp.post('/external-access/analyze')" in route
    assert '@permission_required(\'tenant.manage\')' in route
    assert 'evaluate_tenant_access_drift_committed(' in route
    assert '_csrf()' in route

    assert "'recent_capsule_access_drift'" in context
    assert 'Analyze Access Drift' in template
    assert 'Latest committed Access Drift findings' in template
    assert 'Effective RBAC was not reverified' in template
