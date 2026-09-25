from pathlib import Path


def test_tenant_domain_foundation_keeps_provider_neutral_authority() -> None:
    model_source = Path('app/models/tenant.py').read_text(encoding='utf-8')
    provider_source = Path('app/kubernetes/tenant/providers.py').read_text(encoding='utf-8')
    architecture = Path('docs/architecture/kubernetes-tenant-domain.md').read_text(encoding='utf-8')
    assert "NATIVE_KUBERNETES = 'native_kubernetes'" in provider_source
    assert "CAPSULE = 'capsule'" in provider_source
    assert 'class TenantProvider(Protocol)' in provider_source
    assert 'reconciliation_authority' in model_source
    assert "'managed', 'discovered', 'adopted'" in model_source
    assert 'Kubernetes → Tenant' in architecture
    assert 'not registered as a second endpoint' in architecture
