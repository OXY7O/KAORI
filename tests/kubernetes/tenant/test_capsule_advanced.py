from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_advanced import (
    CapsuleAdvancedResourceKind,
    capsule_resource_descriptor,
    validate_advanced_intent,
)
from app.kubernetes.tenant.capsule_provider import CapsuleDiscoverySnapshot, CapsuleTenantProvider
from app.kubernetes.tenant.providers import TenantCapabilityStatus, TenantProviderError


def _provider(*available: str) -> CapsuleTenantProvider:
    capabilities = {
        'tenant_controller': TenantCapabilityStatus.AVAILABLE,
        'supported_crd_version': TenantCapabilityStatus.AVAILABLE,
        'admission_enforcement': TenantCapabilityStatus.AVAILABLE,
        'proxy': TenantCapabilityStatus.UNAVAILABLE,
        'shared_global_quota': TenantCapabilityStatus.UNAVAILABLE,
        'resource_pools': TenantCapabilityStatus.UNAVAILABLE,
        'replication': TenantCapabilityStatus.UNAVAILABLE,
        'tenant_cordon': TenantCapabilityStatus.UNAVAILABLE,
        'namespace_controls': TenantCapabilityStatus.UNAVAILABLE,
        'resource_rules': TenantCapabilityStatus.UNAVAILABLE,
        'cross_namespace_credential': TenantCapabilityStatus.UNAVAILABLE,
        'self_service_namespace': TenantCapabilityStatus.UNAVAILABLE,
    }
    for key in available:
        capabilities[key] = TenantCapabilityStatus.AVAILABLE
    return CapsuleTenantProvider(
        snapshot=CapsuleDiscoverySnapshot(
            installed=True,
            reported_version='0.14.0',
            tenant_api_versions=('v1beta2',),
            crds=(),
            capabilities=capabilities,
        )
    )


@pytest.mark.parametrize(
    ('kind', 'capability', 'plural', 'namespaced'),
    (
        (CapsuleAdvancedResourceKind.GLOBAL_RESOURCE_QUOTA, 'shared_global_quota', 'globalresourcequotas', False),
        (CapsuleAdvancedResourceKind.RESOURCE_POOL, 'resource_pools', 'resourcepools', False),
        (CapsuleAdvancedResourceKind.RESOURCE_POOL_CLAIM, 'resource_pools', 'resourcepoolclaims', True),
        (CapsuleAdvancedResourceKind.TENANT_RESOURCE, 'replication', 'tenantresources', True),
        (CapsuleAdvancedResourceKind.GLOBAL_TENANT_RESOURCE, 'replication', 'globaltenantresources', False),
    ),
)
def test_resource_descriptor_maps_capsule_scope(kind, capability, plural, namespaced) -> None:
    descriptor = capsule_resource_descriptor(kind)
    assert descriptor.capability == capability
    assert descriptor.plural == plural
    assert descriptor.namespaced is namespaced


def test_advanced_intent_fails_closed_when_capability_is_not_available() -> None:
    intent = SimpleNamespace(
        resource_kind='global_resource_quota',
        provider_key='capsule',
        desired_spec_json={'quota': {'hard': {'requests.cpu': '4'}}},
        namespace=None,
        resource_name='team-shared',
    )

    with pytest.raises(TenantProviderError, match='shared_global_quota'):
        validate_advanced_intent(intent, provider=_provider())


def test_native_or_non_capsule_authority_never_executes_capsule_advanced_intent() -> None:
    intent = SimpleNamespace(
        resource_kind='resource_pool',
        provider_key='native_kubernetes',
        desired_spec_json={'quota': {'hard': {'requests.cpu': '4'}}},
        namespace=None,
        resource_name='team-pool',
    )

    with pytest.raises(ValueError, match='Capsule provider authority'):
        validate_advanced_intent(intent, provider=_provider('resource_pools'))


def test_namespaced_advanced_resource_requires_governed_namespace() -> None:
    intent = SimpleNamespace(
        resource_kind='resource_pool_claim',
        provider_key='capsule',
        desired_spec_json={'pool': 'team-pool', 'claim': {'requests.cpu': '1'}},
        namespace=None,
        resource_name='claim-a',
    )

    with pytest.raises(ValueError, match='namespace'):
        validate_advanced_intent(intent, provider=_provider('resource_pools'))


def test_self_service_namespace_creation_is_not_an_executable_resource_kind() -> None:
    with pytest.raises(ValueError):
        CapsuleAdvancedResourceKind('self_service_namespace')
