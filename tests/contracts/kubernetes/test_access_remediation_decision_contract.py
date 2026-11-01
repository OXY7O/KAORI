import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_remediation_plan_reuses_existing_governed_grant_inspect_reconcile_without_automation():
    service = read('app/kubernetes/tenant/access_remediation_plan.py')
    routes = read('app/kubernetes/tenant/routes_access.py')
    detail = read('app/templates/kubernetes/tenant/partials/_provider_access_evidence_detail.html')
    remediation = read('app/templates/kubernetes/tenant/partials/_provider_access_remediation_detail.html')
    docs = read('docs/architecture/kubernetes-tenant-access-governance.md')

    assert 'latest_tenant_access_drift_evidence(tenant_id)' in service
    assert 'TenantAccessGrant.query.filter_by(tenant_id=tenant_id).all()' in service
    assert "'explicit_grant_reconcile'" in service
    assert "'auto_mutation_performed': False" in service
    assert "'auto_execute': False" in service
    assert re.search(r'db\.session\.add\(\s*AuditEvent\(', service)
    assert 'runtime_adapter.build_client' not in service
    assert 'reconcile_provider_access_grant(' not in service
    assert 'patch_cluster_custom_object(' not in service
    assert 'analyzed_age < 0 or analyzed_age > 900' in service
    assert 'observed_age < 0 or observed_age > 3600' in service
    assert 'source_utc > evaluated_utc' in service
    assert 'grant changed after drift analysis' in service.lower()

    assert "@tenant_bp.post('/external-access/plan-remediation')" in routes
    assert 'prepare_tenant_access_remediation_plan_committed(' in routes
    assert '_csrf()' in routes
    assert 'Prepare Remediation Decisions' in detail
    assert 'Governed Remediation' in remediation
    assert 'no kubernetes mutation' in remediation.lower()
    assert 'Technical Evidence' in remediation
    assert 'Access Grant Inspect' in docs
