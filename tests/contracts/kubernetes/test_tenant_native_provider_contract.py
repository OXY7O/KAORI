from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _discovery_source() -> str:
    return (
        _read('app/kubernetes/tenant/discovery_service.py')
        + '\n'
        + _read('app/kubernetes/tenant/discovery_adoption.py')
    )


def test_kubernetes_discovery_exposes_optional_tenant_mutation_capabilities() -> None:
    compatibility = (
        ROOT / 'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/compatibility.py'
    ).read_text(encoding='utf-8')

    for capability in (
        'tenant.namespaces',
        'tenant.resourcequotas',
        'tenant.limitranges',
        'tenant.rbac.roles',
        'tenant.rbac.rolebindings',
        'tenant.serviceaccounts',
        'tenant.serviceaccount_tokens',
        'tenant.secrets',
        'tenant.admission.validatingpolicies',
        'tenant.admission.validatingpolicybindings',
    ):
        assert capability in compatibility


def test_native_provider_reuses_canonical_provider_contract() -> None:
    providers = (ROOT / 'app/kubernetes/tenant/providers.py').read_text(encoding='utf-8')
    native = (ROOT / 'app/kubernetes/tenant/native_provider.py').read_text(encoding='utf-8')

    assert 'class TenantProviderOperationResult' in providers
    assert 'class TenantProviderError' in providers
    assert 'class NativeKubernetesTenantProvider' in native
    assert 'TenantProviderKey.NATIVE_KUBERNETES' in native
    assert 'discovery_summary' in native
    assert 'provider_evidence_json' in native
    assert 'secret_material_persisted' in native


def test_native_provider_readiness_is_capability_scoped_for_degraded_integrations() -> None:
    native = (ROOT / 'app/kubernetes/tenant/native_provider.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/service.py').read_text(encoding='utf-8')
    discovery = _discovery_source()

    assert "_WORKSPACE_READINESS = frozenset({'ready', 'degraded'})" in native
    assert 'def effective_native_connection_readiness' in native
    assert 'def tenant_workspace_connection_available' in native
    assert 'readiness not in _WORKSPACE_READINESS' in native
    assert 'tenant_workspace_connection_available(cluster.kubernetes_connection)' in service
    assert 'tenant_workspace_connection_available(cluster.kubernetes_connection)' in discovery
    assert "KubernetesConnection.readiness_status == 'ready'" not in discovery


def test_native_provider_wraps_existing_reconcilers_instead_of_cloning_them() -> None:
    native = (ROOT / 'app/kubernetes/tenant/native_provider.py').read_text(encoding='utf-8')

    assert 'reconcile_native_namespace' in native
    assert 'reconcile_native_access_grant' in native
    assert 'reconcile_native_credential' in native
    assert 'reconcile_native_managed_resource' in native


def test_security_sensitive_policy_capability_is_fail_closed() -> None:
    native = (ROOT / 'app/kubernetes/tenant/native_provider.py').read_text(encoding='utf-8')

    assert 'def require_native_capability(' in native
    assert "'admission_enforcement'" in native
    assert 'TenantCapabilityStatus.AVAILABLE' in native


def test_native_provider_architecture_is_documented_without_capsule_dependency() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-native-provider.md').read_text(encoding='utf-8')

    assert 'Native Kubernetes' in docs
    assert 'capability matrix' in docs
    assert 'fail closed' in docs
    assert 'Capsule' in docs
    assert 'does not require Capsule' in docs
