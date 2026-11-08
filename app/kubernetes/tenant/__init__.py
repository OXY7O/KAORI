"""Provider-neutral Kubernetes Tenant domain foundation."""

from app.kubernetes.tenant.providers import (
    ProviderAuthorityTransition,
    TenantProvider,
    TenantProviderCapability,
    TenantProviderResult,
    validate_authority_transition,
)

__all__ = [
    'ProviderAuthorityTransition',
    'TenantProvider',
    'TenantProviderCapability',
    'TenantProviderResult',
    'validate_authority_transition',
]
