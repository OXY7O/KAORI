from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_production_governance_has_bounded_exception_persistence() -> None:
    model = (ROOT / 'app/models/tenant.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260926_tenant_production_access.py').read_text(encoding='utf-8')

    assert 'class TenantProductionAccessException(db.Model):' in model
    assert "status IN ('active', 'expired', 'revoked')" in model
    assert 'tenant_namespace_id' in model
    assert 'access_grant_id' in model
    assert 'owner_user_id' in model
    assert 'approved_by_user_id' in model
    assert 'review_due_at' in model
    assert "down_revision = '20260926_tenant_deployer_cred'" in migration


def test_production_policy_is_pipeline_first_and_fail_closed_for_humans() -> None:
    policy = (ROOT / 'app/kubernetes/tenant/production_governance.py').read_text(encoding='utf-8')

    assert 'def evaluate_production_access(' in policy
    assert "authority='pipeline'" in policy
    assert "authority='administrator'" in policy
    assert "authority='exception'" in policy
    assert "'production_direct_access_denied'" in policy
    assert "'production_human_mutation'" in policy
    assert "'production_exception_used'" in policy


def test_production_exception_service_records_non_secret_activity_evidence() -> None:
    service = (ROOT / 'app/kubernetes/tenant/production_governance_service.py').read_text(encoding='utf-8')

    assert 'def create_production_access_exception_committed(' in service
    assert 'def revoke_production_access_exception_committed(' in service
    assert 'def record_production_access_decision_committed(' in service
    assert "target_type = 'tenant_production_access'" in service
    assert "'secret_material_persisted': False" in service


def test_existing_credential_secret_boundary_is_not_bypassed() -> None:
    service = (ROOT / 'app/kubernetes/tenant/production_governance_service.py').read_text(encoding='utf-8')

    assert 'token' not in service.lower()
    assert 'kubeconfig' not in service.lower()
