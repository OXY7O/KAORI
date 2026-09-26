from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_capsule_discovery_uses_supported_api_and_explicit_probes() -> None:
    source = (ROOT / 'app/kubernetes/tenant/capsule_provider.py').read_text(encoding='utf-8')

    assert "capsule.clastix.io" in source
    assert "v1beta2" in source
    assert "v1beta1" in source
    assert "tenants.capsule.clastix.io" in source
    assert "tenantresources.capsule.clastix.io" in source
    assert "globaltenantresources.capsule.clastix.io" in source
    assert "globalresourcequotas.capsule.clastix.io" in source
    assert "resourcepools.capsule.clastix.io" in source
    assert "resourcepoolclaims.capsule.clastix.io" in source
    assert "probes.get('proxy')" in source
    assert "probes.get('admission_enforcement')" in source


def test_capsule_provider_has_degraded_and_native_recovery_contract() -> None:
    source = (ROOT / 'app/kubernetes/tenant/capsule_provider.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/capsule_service.py').read_text(encoding='utf-8')

    assert 'class CapsuleTenantProvider' in source
    assert 'def validate_native_recovery_readiness(' in source
    assert 'TenantProviderState.CAPSULE_DEGRADED' in source
    assert 'TenantProviderState.NATIVE_RECOVERY' in service
    assert 'def observe_capsule_provider_committed(' in service
    assert 'def begin_native_recovery_committed(' in service
    assert 'def complete_native_recovery_committed(' in service


def test_capsule_service_preserves_single_authority_until_recovery_verification() -> None:
    service = (ROOT / 'app/kubernetes/tenant/capsule_service.py').read_text(encoding='utf-8')

    assert "tenant.reconciliation_authority = 'capsule'" in service
    assert "tenant.reconciliation_authority = 'native_kubernetes'" in service
    assert 'validate_authority_transition' in service
    assert "'secret_material_persisted': False" in service


def test_capsule_architecture_documents_no_automatic_fallback() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-capsule-provider.md').read_text(encoding='utf-8')

    assert 'Capsule Degraded' in docs
    assert 'Native Recovery' in docs
    assert 'no automatic fallback' in docs
    assert 'single reconciliation authority' in docs
    assert 'v1beta2' in docs
