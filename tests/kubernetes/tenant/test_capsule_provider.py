from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_provider import (
    CapsuleTenantProvider,
    discover_capsule,
    require_capsule_capability,
    validate_native_recovery_readiness,
)
from app.kubernetes.tenant.providers import (
    TenantCapabilityStatus,
    TenantProviderError,
    TenantProviderState,
)


class _ApiClient:
    def __init__(self, crds):
        self.crds = crds

    def call_api(self, path, method, **kwargs):
        assert path == '/apis/apiextensions.k8s.io/v1/customresourcedefinitions'
        assert method == 'GET'
        return {'items': self.crds}


def _crd(name, versions=('v1beta2',), *, reported_version='0.14.0'):
    return {
        'metadata': {
            'name': name,
            'labels': {'app.kubernetes.io/version': reported_version},
        },
        'spec': {
            'group': 'capsule.clastix.io',
            'versions': [{'name': version, 'served': True} for version in versions],
        },
    }


def _full_crds():
    return [
        _crd('tenants.capsule.clastix.io'),
        _crd('tenantresources.capsule.clastix.io'),
        _crd('globaltenantresources.capsule.clastix.io'),
        _crd('globalresourcequotas.capsule.clastix.io'),
        _crd('resourcepools.capsule.clastix.io'),
        _crd('resourcepoolclaims.capsule.clastix.io'),
    ]


def test_capsule_discovery_is_capability_aware_not_boolean() -> None:
    snapshot = discover_capsule(
        _ApiClient(_full_crds()),
        probes={'admission_enforcement': True, 'proxy': True},
    )
    assert snapshot.installed is True
    assert snapshot.reported_version == '0.14.0'
    assert 'v1beta2' in snapshot.tenant_api_versions
    assert snapshot.capabilities['tenant_controller'] is TenantCapabilityStatus.AVAILABLE
    assert snapshot.capabilities['admission_enforcement'] is TenantCapabilityStatus.AVAILABLE
    assert snapshot.capabilities['proxy'] is TenantCapabilityStatus.AVAILABLE
    assert snapshot.capabilities['shared_global_quota'] is TenantCapabilityStatus.AVAILABLE
    assert snapshot.capabilities['resource_pools'] is TenantCapabilityStatus.AVAILABLE
    assert snapshot.capabilities['replication'] is TenantCapabilityStatus.AVAILABLE


def test_crd_presence_does_not_fake_proxy_or_admission_readiness() -> None:
    snapshot = discover_capsule(_ApiClient(_full_crds()))
    assert snapshot.capabilities['tenant_controller'] is TenantCapabilityStatus.AVAILABLE
    assert snapshot.capabilities['admission_enforcement'] is TenantCapabilityStatus.UNAVAILABLE
    assert snapshot.capabilities['proxy'] is TenantCapabilityStatus.UNAVAILABLE


def test_unsupported_tenant_api_version_is_degraded_and_fails_sensitive_capability() -> None:
    snapshot = discover_capsule(
        _ApiClient([_crd('tenants.capsule.clastix.io', versions=('v1alpha1',))]),
        probes={'admission_enforcement': True},
    )
    provider = CapsuleTenantProvider(snapshot=snapshot)
    result = provider.validate_binding(cluster_id='cluster-a')
    assert result.state is TenantProviderState.CAPSULE_DEGRADED
    with pytest.raises(TenantProviderError, match='tenant_controller'):
        require_capsule_capability(provider, cluster_id='cluster-a', capability='tenant_controller')


def test_capsule_provider_rejects_dual_authority() -> None:
    snapshot = discover_capsule(
        _ApiClient(_full_crds()),
        probes={'admission_enforcement': True},
    )
    provider = CapsuleTenantProvider(snapshot=snapshot)
    tenant = SimpleNamespace(provider_key='native_kubernetes', provider_state='native')
    with pytest.raises(ValueError, match='Capsule authority'):
        provider.validate_tenant_authority(tenant)


def test_native_recovery_requires_materialized_verified_equivalents() -> None:
    snapshot = discover_capsule(
        _ApiClient(_full_crds()),
        probes={'admission_enforcement': False},
    )
    native = {
        'namespace': TenantCapabilityStatus.AVAILABLE,
        'resource_quota': TenantCapabilityStatus.AVAILABLE,
        'limit_range': TenantCapabilityStatus.AVAILABLE,
        'namespaced_rbac': TenantCapabilityStatus.AVAILABLE,
        'service_account_token': TenantCapabilityStatus.AVAILABLE,
        'managed_tls': TenantCapabilityStatus.AVAILABLE,
        'managed_registry': TenantCapabilityStatus.AVAILABLE,
    }
    materialized = set(native)

    with pytest.raises(ValueError, match='verified'):
        validate_native_recovery_readiness(
            snapshot=snapshot,
            native_capabilities=native,
            materialized_capabilities=materialized,
            verified=False,
        )

    validate_native_recovery_readiness(
        snapshot=snapshot,
        native_capabilities=native,
        materialized_capabilities=materialized,
        verified=True,
    )


def test_native_recovery_fails_when_native_equivalent_is_unavailable() -> None:
    snapshot = discover_capsule(_ApiClient(_full_crds()))
    native = {
        'namespace': TenantCapabilityStatus.AVAILABLE,
        'resource_quota': TenantCapabilityStatus.UNAVAILABLE,
        'limit_range': TenantCapabilityStatus.AVAILABLE,
        'namespaced_rbac': TenantCapabilityStatus.AVAILABLE,
        'service_account_token': TenantCapabilityStatus.AVAILABLE,
        'managed_tls': TenantCapabilityStatus.AVAILABLE,
        'managed_registry': TenantCapabilityStatus.AVAILABLE,
    }
    with pytest.raises(ValueError, match='resource_quota'):
        validate_native_recovery_readiness(
            snapshot=snapshot,
            native_capabilities=native,
            materialized_capabilities=set(native),
            verified=True,
        )
