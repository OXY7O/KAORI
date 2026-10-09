from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_remediation_plan_reuses_existing_governed_grant_inspect_reconcile_without_automation():
    service = read('app/kubernetes/tenant/access_remediation_plan.py')
    routes = read('app/kubernetes/tenant/routes_access.py')
    panel = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    docs = read('docs/architecture/kubernetes-tenant-access-governance.md')

    assert 'latest_tenant_access_drift_evidence(tenant_id)' in service
    assert 'TenantAccessGrant.query.filter_by(tenant_id=tenant_id).all()' in service
    assert "'explicit_grant_reconcile'" in service
    assert "'auto_mutation_performed': False" in service
    assert "'auto_execute': False" in service
    assert 'db.session.add(AuditEvent(' in service
    assert 'runtime_adapter.build_client' not in service
    assert 'reconcile_provider_access_grant(' not in service
    assert 'patch_cluster_custom_object(' not in service
    assert "age < 0 or age > 900" in service
    assert 'grant changed after drift analysis' in service.lower()

    assert "@tenant_bp.post('/external-access/plan-remediation')" in routes
    assert 'prepare_tenant_access_remediation_plan_committed(' in routes
    assert '_csrf()' in routes
    assert 'Prepare Remediation Decisions' in panel
    assert 'Governed Remediation Decisions' in panel
    assert 'no kubernetes mutation' in panel.lower()
    assert 'Access Grant Inspect' in docs
