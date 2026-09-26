from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.native_provider import (
    NativeKubernetesTenantProvider,
    require_native_capability,
)
from app.kubernetes.tenant.providers import TenantCapabilityStatus, TenantProviderState


def _connection(*, readiness='ready', features=None):
    return SimpleNamespace(
        readiness_status=readiness,
        compatibility_status='compatible',
        detected_version='v1.29.5',
        discovery_summary={'features': features or {}, 'api_profile': 'kubernetes-core-v1'},
    )


def _feature(status='ready', *, message='ready'):
    return {'status': status, 'message': message, 'selected_api': {'group': '', 'version': 'v1', 'resource': 'x'}}


def test_native_capability_matrix_distinguishes_available_degraded_unavailable_and_not_applicable() -> None:
    features = {
        'tenant.namespaces': _feature(),
        'tenant.resourcequotas': _feature(),
        'tenant.limitranges': _feature(),
        'tenant.rbac.roles': _feature(),
        'tenant.rbac.rolebindings': _feature(),
        'tenant.serviceaccounts': _feature(),
        'tenant.serviceaccount_tokens': _feature(),
        'tenant.secrets': _feature(),
        'tenant.admission.validatingpolicies': _feature('legacy', message='beta API'),
        'tenant.admission.validatingpolicybindings': _feature('blocked', message='not served'),
    }
    provider = NativeKubernetesTenantProvider(connection=_connection(features=features))
    capabilities = {item.key: item for item in provider.capabilities(cluster_id='cluster-a')}

    assert capabilities['namespace'].status is TenantCapabilityStatus.AVAILABLE
    assert capabilities['managed_registry'].status is TenantCapabilityStatus.AVAILABLE
    assert capabilities['admission_enforcement'].status is TenantCapabilityStatus.UNAVAILABLE
    assert capabilities['external_registry_provider'].status is TenantCapabilityStatus.NOT_APPLICABLE


def test_connection_degraded_propagates_to_baseline_capabilities() -> None:
    provider = NativeKubernetesTenantProvider(connection=_connection(readiness='degraded'))
    capabilities = provider.capabilities(cluster_id='cluster-a')
    assert all(
        item.status in {TenantCapabilityStatus.DEGRADED, TenantCapabilityStatus.NOT_APPLICABLE}
        for item in capabilities
    )


def test_security_sensitive_capability_fails_closed() -> None:
    provider = NativeKubernetesTenantProvider(connection=_connection(features={
        'tenant.admission.validatingpolicies': _feature('blocked'),
        'tenant.admission.validatingpolicybindings': _feature('blocked'),
    }))
    with pytest.raises(ValueError, match='admission_enforcement'):
        require_native_capability(provider, cluster_id='cluster-a', capability='admission_enforcement')


def test_native_provider_rejects_capsule_authority() -> None:
    tenant = SimpleNamespace(provider_key='capsule', provider_state=TenantProviderState.CAPSULE.value)
    provider = NativeKubernetesTenantProvider(connection=_connection())
    with pytest.raises(ValueError, match='Native Kubernetes authority'):
        provider.validate_tenant_authority(tenant)


def test_provider_result_is_non_secret_and_separates_desired_from_effective() -> None:
    provider = NativeKubernetesTenantProvider(connection=_connection())
    result = provider.operation_result(
        operation='namespace.reconcile',
        capability='namespace',
        status='ready',
        desired_hash='desired',
        effective_hash='effective',
        evidence={'resource': 'payments-prod'},
    )
    assert result.provider_key.value == 'native_kubernetes'
    assert result.desired_hash == 'desired'
    assert result.effective_hash == 'effective'
    assert 'credential' not in repr(result).lower()
