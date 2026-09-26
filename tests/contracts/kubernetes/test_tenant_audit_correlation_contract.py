from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_audit_observation_model_is_normalized_and_retention_aware() -> None:
    model = (ROOT / 'app/models/tenant_audit.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260927_tenant_audit.py').read_text(encoding='utf-8')

    assert 'class TenantKubernetesAuditObservation(db.Model):' in model
    assert 'event_uid' in model
    assert 'source_id' in model
    assert 'correlation_status' in model
    assert 'expires_at' in model
    assert "UNIQUE" not in migration.upper() or 'event_uid' in migration
    assert "sa.Column('request_object'" not in migration
    assert "sa.Column('response_object'" not in migration
    assert "sa.Column('body'" not in migration
    assert "down_revision = '20260926_tenant_domain_policy'" in migration


def test_audit_ingestion_is_idempotent_and_non_secret() -> None:
    service = (ROOT / 'app/kubernetes/tenant/audit_service.py').read_text(encoding='utf-8')

    assert 'def ingest_kubernetes_audit_event_committed(' in service
    assert 'TenantKubernetesAuditObservation.query.filter_by(event_uid=' in service
    assert 'def purge_expired_tenant_audit_observations_committed(' in service
    assert "'secret_material_persisted': False" in service
    assert 'requestObject' not in service
    assert 'responseObject' not in service


def test_correlation_maps_managed_credentials_and_keeps_unknown_explicit() -> None:
    source = (ROOT / 'app/kubernetes/tenant/audit_correlation.py').read_text(encoding='utf-8')

    assert 'class TenantAuditPrincipalCandidate' in source
    assert "status='managed'" in source
    assert "status='managed_revoked'" in source
    assert "status='unmanaged'" in source
    assert "status='ambiguous'" in source
    assert 'service_account_name' in source


def test_architecture_does_not_duplicate_raw_audit_log_store() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-audit-correlation.md').read_text(encoding='utf-8')

    assert 'not a raw audit-log mirror' in docs
    assert 'idempotent' in docs
    assert 'unmanaged' in docs
    assert 'JumpServer' in docs
    assert 'secret' in docs.lower()
