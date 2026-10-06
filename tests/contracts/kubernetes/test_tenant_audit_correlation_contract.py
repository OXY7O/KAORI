from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tenant_audit_evidence_model_is_minimal_and_idempotent() -> None:
    model = (ROOT / 'app/models/tenant_audit.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260927_tenant_audit_corr.py').read_text(encoding='utf-8')

    assert 'class TenantAuditEvidence(db.Model):' in model
    assert 'idempotency_key' in model
    assert 'source_event_id' in model
    assert 'principal_username' in model
    assert 'correlation_status' in model
    assert 'credential_id' in model
    assert 'access_grant_id' in model
    assert 'owner_user_id' in model
    assert 'jumpserver_reference' in model
    assert 'retention_class' in model
    assert "down_revision = '20260926_tenant_domain_policy'" in migration
    assert 'request_object' not in model.lower()
    assert 'response_object' not in model.lower()
    assert 'raw_payload' not in model.lower()


def test_ingestion_boundary_is_bounded_idempotent_and_projects_activity() -> None:
    service = (ROOT / 'app/kubernetes/tenant/audit_correlation_service.py').read_text(encoding='utf-8')

    assert 'def ingest_kubernetes_audit_events_committed(' in service
    assert 'def correlate_kubernetes_principal(' in service
    assert 'idempotency_key' in service
    assert "_EVENT_TYPE = 'kubernetes_tenant_audit'" in service
    assert 'activity.event_type = _EVENT_TYPE' in service
    assert 'deck_visible = False' in service
    assert "'secret_material_persisted': False" in service
    assert 'requestObject' not in service
    assert 'responseObject' not in service


def test_audit_evidence_reuses_data_lifecycle_retention_framework() -> None:
    registry = (ROOT / 'app/platform_operations/data_lifecycle/retention/domains/__init__.py').read_text(
        encoding='utf-8'
    )
    domain = (ROOT / 'app/platform_operations/data_lifecycle/retention/domains/tenant_audit_evidence.py').read_text(
        encoding='utf-8'
    )

    assert "'tenant_audit_evidence': TenantAuditEvidenceArchiveDomain" in registry
    assert "name = 'tenant_audit_evidence'" in domain
    assert "source_model = 'tenant_audit_evidence'" in domain
    assert 'TenantAuditEvidence' in domain
    assert "'secret_material_persisted': False" in domain


def test_architecture_documents_unknown_identity_and_no_raw_log_copy() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-audit-correlation.md').read_text(encoding='utf-8')

    assert 'unknown or unmanaged' in docs
    assert 'raw Kubernetes audit log' in docs
    assert 'idempotent' in docs
    assert 'JumpServer' in docs
    assert 'secret values' in docs
