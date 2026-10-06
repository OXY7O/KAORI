from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_managed_resource_model_records_intent_without_secret_payload() -> None:
    model = (ROOT / 'app/models/tenant_managed_resource.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260926_tenant_managed_resources.py').read_text(encoding='utf-8')

    assert 'class TenantManagedResourceIntent(db.Model):' in model
    assert "TLS = 'tls'" in model
    assert "REGISTRY = 'registry'" in model
    assert "PLATFORM_TLS = 'platform_tls'" in model
    assert "NAMESPACE_TLS_COMPAT = 'namespace_tls_compat'" in model
    assert "IMAGE_PULL_SECRET = 'image_pull_secret'" in model
    assert "EXTERNAL_CREDENTIAL_PROVIDER = 'external_credential_provider'" in model
    assert 'source_reference' in model
    assert 'rotation_generation' in model
    assert "sa.Column('data'" not in migration
    assert "sa.Column('secret'" not in migration
    assert "down_revision = '20260926_tenant_prod_access'" in migration


def test_native_reconciliation_marks_platform_security_ownership_and_never_persists_values() -> None:
    reconciliation = (ROOT / 'app/kubernetes/tenant/managed_resources.py').read_text(encoding='utf-8')

    assert 'app.kubernetes.io/managed-by' in reconciliation
    assert 'kaori.io/platform-security' in reconciliation
    assert 'V1Secret' in reconciliation
    assert 'kubernetes.io/tls' in reconciliation
    assert 'kubernetes.io/dockerconfigjson' in reconciliation
    assert "'secret_material_persisted': False" in reconciliation
    assert 'payload_digest' in reconciliation


def test_managed_resource_lifecycle_has_rotation_and_removal_evidence() -> None:
    service = (ROOT / 'app/kubernetes/tenant/managed_resource_service.py').read_text(encoding='utf-8')

    assert 'def create_managed_resource_intent_committed(' in service
    assert 'def rotate_managed_resource_committed(' in service
    assert 'def remove_managed_resource_committed(' in service
    assert "action='tenant.managed_resource.created'" in service
    assert "action='tenant.managed_resource.rotated'" in service
    assert "action='tenant.managed_resource.removed'" in service


def test_architecture_documents_platform_tls_preference_and_registry_secret_boundary() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-managed-resources.md').read_text(encoding='utf-8')

    assert 'Platform TLS' in docs
    assert 'compatibility mode' in docs
    assert 'image-pull Secret' in docs
    assert 'secret material is never persisted' in docs
