from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class TenantProviderKey(StrEnum):
    NATIVE_KUBERNETES = 'native_kubernetes'
    CAPSULE = 'capsule'


class TenantProviderState(StrEnum):
    NATIVE = 'native'
    CAPSULE = 'capsule'
    CAPSULE_DEGRADED = 'capsule_degraded'
    NATIVE_RECOVERY = 'native_recovery'


class TenantCapabilityStatus(StrEnum):
    AVAILABLE = 'available'
    DEGRADED = 'degraded'
    UNAVAILABLE = 'unavailable'
    NOT_APPLICABLE = 'not_applicable'


@dataclass(frozen=True, slots=True)
class TenantProviderCapability:
    key: str
    status: TenantCapabilityStatus
    message: str = ''


@dataclass(frozen=True, slots=True)
class TenantProviderResult:
    provider_key: TenantProviderKey
    state: TenantProviderState
    capabilities: tuple[TenantProviderCapability, ...]
    evidence_reference: str | None = None


@dataclass(frozen=True, slots=True)
class TenantProviderOperationResult:
    provider_key: TenantProviderKey
    operation: str
    capability: str
    status: str
    desired_hash: str | None = None
    effective_hash: str | None = None
    evidence: dict[str, object] | None = None
    message: str = ''
    error_code: str | None = None


class TenantProviderError(RuntimeError):
    """Provider-neutral Tenant operation failure with non-secret evidence."""

    def __init__(self, code: str, message: str, *, capability: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.capability = capability


@dataclass(frozen=True, slots=True)
class ProviderAuthorityTransition:
    current_provider: TenantProviderKey
    target_provider: TenantProviderKey
    current_state: TenantProviderState
    recovery_verified: bool = False


@runtime_checkable
class TenantProvider(Protocol):
    """Provider-neutral contract implemented by Native Kubernetes and Capsule."""

    provider_key: TenantProviderKey

    def capabilities(self, *, cluster_id: str) -> tuple[TenantProviderCapability, ...]:
        """Return observed capability evidence for the selected cluster."""
        ...

    def validate_binding(self, *, cluster_id: str) -> TenantProviderResult:
        """Validate whether this provider may become authority for a tenant."""
        ...


def validate_authority_transition(transition: ProviderAuthorityTransition) -> None:
    """Reject implicit provider failover and unverified recovery authority transfer."""
    if transition.current_provider == transition.target_provider:
        return
    if transition.current_state is not TenantProviderState.NATIVE_RECOVERY:
        raise ValueError('tenant provider authority changes require explicit native recovery state')
    if not transition.recovery_verified:
        raise ValueError('tenant provider authority changes require verified recovery evidence')
