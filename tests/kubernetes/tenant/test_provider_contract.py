import pytest

from app.kubernetes.tenant.providers import (
    ProviderAuthorityTransition,
    TenantCapabilityStatus,
    TenantProviderKey,
    TenantProviderState,
    validate_authority_transition,
)


def test_provider_keys_keep_native_and_capsule_behind_one_tenant_contract() -> None:
    assert {item.value for item in TenantProviderKey} == {'native_kubernetes', 'capsule'}
    assert TenantCapabilityStatus.UNAVAILABLE.value == 'unavailable'


def test_same_provider_does_not_require_recovery_transition() -> None:
    validate_authority_transition(ProviderAuthorityTransition(current_provider=TenantProviderKey.CAPSULE, target_provider=TenantProviderKey.CAPSULE, current_state=TenantProviderState.CAPSULE_DEGRADED))


def test_provider_change_fails_closed_without_native_recovery() -> None:
    with pytest.raises(ValueError, match='explicit native recovery'):
        validate_authority_transition(ProviderAuthorityTransition(current_provider=TenantProviderKey.CAPSULE, target_provider=TenantProviderKey.NATIVE_KUBERNETES, current_state=TenantProviderState.CAPSULE_DEGRADED))


def test_provider_change_requires_verified_recovery_evidence() -> None:
    transition = ProviderAuthorityTransition(current_provider=TenantProviderKey.CAPSULE, target_provider=TenantProviderKey.NATIVE_KUBERNETES, current_state=TenantProviderState.NATIVE_RECOVERY)
    with pytest.raises(ValueError, match='verified recovery evidence'):
        validate_authority_transition(transition)
    validate_authority_transition(ProviderAuthorityTransition(current_provider=TenantProviderKey.CAPSULE, target_provider=TenantProviderKey.NATIVE_KUBERNETES, current_state=TenantProviderState.NATIVE_RECOVERY, recovery_verified=True))
