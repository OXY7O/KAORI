from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.kubernetes.tenant.providers import (
    TenantCapabilityStatus,
    TenantProviderCapability,
    TenantProviderError,
    TenantProviderKey,
    TenantProviderResult,
    TenantProviderState,
)

_CAPSULE_GROUP = 'capsule.clastix.io'
_SUPPORTED_API_VERSIONS = frozenset({'v1beta2', 'v1beta1'})
_TENANT_CRD = 'tenants.capsule.clastix.io'
_TENANT_RESOURCE_CRD = 'tenantresources.capsule.clastix.io'
_GLOBAL_TENANT_RESOURCE_CRD = 'globaltenantresources.capsule.clastix.io'
_GLOBAL_RESOURCE_QUOTA_CRD = 'globalresourcequotas.capsule.clastix.io'
_RESOURCE_POOL_CRD = 'resourcepools.capsule.clastix.io'
_RESOURCE_POOL_CLAIM_CRD = 'resourcepoolclaims.capsule.clastix.io'
_RECOVERY_NATIVE_CAPABILITIES = frozenset(
    {
        'namespace',
        'resource_quota',
        'limit_range',
        'namespaced_rbac',
        'service_account_token',
        'managed_tls',
        'managed_registry',
    }
)


@dataclass(frozen=True, slots=True)
class CapsuleDiscoverySnapshot:
    installed: bool
    reported_version: str | None
    tenant_api_versions: tuple[str, ...]
    crds: tuple[str, ...]
    capabilities: dict[str, TenantCapabilityStatus]

    def as_dict(self) -> dict[str, object]:
        return {
            'installed': self.installed,
            'reported_version': self.reported_version,
            'tenant_api_versions': list(self.tenant_api_versions),
            'crds': list(self.crds),
            'capabilities': {key: value.value for key, value in self.capabilities.items()},
            'secret_material_persisted': False,
        }


def _value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _items(payload: Any, key: str) -> list[Any]:
    value = _value(payload, key, default=[]) or []
    return list(value)


def _metadata_label(item: Any, key: str) -> str | None:
    metadata = _value(item, 'metadata', default={}) or {}
    labels = _value(metadata, 'labels', default={}) or {}
    value = _value(labels, key)
    return str(value) if value else None


def _served_versions(item: Any) -> tuple[str, ...]:
    spec = _value(item, 'spec', default={}) or {}
    versions = []
    for version in _items(spec, 'versions'):
        if bool(_value(version, 'served', default=False)):
            name = str(_value(version, 'name', default='') or '')
            if name:
                versions.append(name)
    return tuple(sorted(set(versions)))


def _controller_status(tenant_versions: tuple[str, ...]) -> TenantCapabilityStatus:
    if not tenant_versions:
        return TenantCapabilityStatus.UNAVAILABLE
    if set(tenant_versions) & _SUPPORTED_API_VERSIONS:
        return TenantCapabilityStatus.AVAILABLE
    return TenantCapabilityStatus.DEGRADED


def _dependent_status(
    *,
    controller_status: TenantCapabilityStatus,
    ready: bool,
) -> TenantCapabilityStatus:
    if not ready:
        return TenantCapabilityStatus.UNAVAILABLE
    if controller_status is TenantCapabilityStatus.AVAILABLE:
        return TenantCapabilityStatus.AVAILABLE
    if controller_status is TenantCapabilityStatus.DEGRADED:
        return TenantCapabilityStatus.DEGRADED
    return TenantCapabilityStatus.UNAVAILABLE


def discover_capsule(
    api_client,
    *,
    probes: dict[str, bool] | None = None,
) -> CapsuleDiscoverySnapshot:
    probes = probes or {}
    payload = api_client.call_api(
        '/apis/apiextensions.k8s.io/v1/customresourcedefinitions',
        'GET',
        response_types_map={200: 'object'},
        auth_settings=['BearerToken'],
        _return_http_data_only=True,
    )
    capsule_items: dict[str, Any] = {}
    for item in _items(payload, 'items'):
        spec = _value(item, 'spec', default={}) or {}
        if str(_value(spec, 'group', default='') or '') != _CAPSULE_GROUP:
            continue
        metadata = _value(item, 'metadata', default={}) or {}
        name = str(_value(metadata, 'name', default='') or '')
        if name:
            capsule_items[name] = item

    tenant_item = capsule_items.get(_TENANT_CRD)
    tenant_versions = _served_versions(tenant_item) if tenant_item is not None else ()
    controller_status = _controller_status(tenant_versions)
    installed = tenant_item is not None

    reported_version = None
    if tenant_item is not None:
        reported_version = _metadata_label(tenant_item, 'app.kubernetes.io/version')
    if reported_version is None:
        for item in capsule_items.values():
            reported_version = _metadata_label(item, 'app.kubernetes.io/version')
            if reported_version is not None:
                break

    capabilities = {
        'tenant_controller': controller_status,
        'supported_crd_version': controller_status,
        'admission_enforcement': _dependent_status(
            controller_status=controller_status,
            ready=bool(probes.get('admission_enforcement')),
        ),
        'proxy': _dependent_status(
            controller_status=controller_status,
            ready=bool(probes.get('proxy')),
        ),
        'shared_global_quota': _dependent_status(
            controller_status=controller_status,
            ready=_GLOBAL_RESOURCE_QUOTA_CRD in capsule_items,
        ),
        'resource_pools': _dependent_status(
            controller_status=controller_status,
            ready=(_RESOURCE_POOL_CRD in capsule_items and _RESOURCE_POOL_CLAIM_CRD in capsule_items),
        ),
        'replication': _dependent_status(
            controller_status=controller_status,
            ready=(_TENANT_RESOURCE_CRD in capsule_items and _GLOBAL_TENANT_RESOURCE_CRD in capsule_items),
        ),
        'tenant_cordon': _dependent_status(
            controller_status=controller_status,
            ready=bool(probes.get('tenant_cordon')),
        ),
        'namespace_controls': _dependent_status(
            controller_status=controller_status,
            ready=bool(probes.get('namespace_controls')),
        ),
        'resource_rules': _dependent_status(
            controller_status=controller_status,
            ready=bool(probes.get('resource_rules')),
        ),
        'cross_namespace_credential': _dependent_status(
            controller_status=controller_status,
            ready=bool(probes.get('cross_namespace_credential')),
        ),
        'self_service_namespace': _dependent_status(
            controller_status=controller_status,
            ready=bool(probes.get('self_service_namespace')),
        ),
    }
    return CapsuleDiscoverySnapshot(
        installed=installed,
        reported_version=reported_version,
        tenant_api_versions=tenant_versions,
        crds=tuple(sorted(capsule_items)),
        capabilities=capabilities,
    )


class CapsuleTenantProvider:
    provider_key = TenantProviderKey.CAPSULE

    def __init__(self, *, snapshot: CapsuleDiscoverySnapshot) -> None:
        self.snapshot = snapshot

    def capabilities(self, *, cluster_id: str) -> tuple[TenantProviderCapability, ...]:
        del cluster_id
        return tuple(
            TenantProviderCapability(
                key=key,
                status=status,
                message=(
                    'Capsule capability is available from explicit discovery/probe evidence.'
                    if status is TenantCapabilityStatus.AVAILABLE
                    else 'Capsule capability is not fully available; sensitive mutations must fail closed.'
                ),
            )
            for key, status in sorted(self.snapshot.capabilities.items())
        )

    def validate_binding(self, *, cluster_id: str) -> TenantProviderResult:
        capabilities = self.capabilities(cluster_id=cluster_id)
        status_by_key = {item.key: item.status for item in capabilities}
        healthy = (
            status_by_key.get('tenant_controller') is TenantCapabilityStatus.AVAILABLE
            and status_by_key.get('admission_enforcement') is TenantCapabilityStatus.AVAILABLE
        )
        state = TenantProviderState.CAPSULE if healthy else TenantProviderState.CAPSULE_DEGRADED
        return TenantProviderResult(
            provider_key=self.provider_key,
            state=state,
            capabilities=capabilities,
            evidence_reference='capsule_discovery',
        )

    def validate_tenant_authority(self, tenant) -> None:
        provider_key = str(getattr(tenant, 'provider_key', '') or '')
        if provider_key != TenantProviderKey.CAPSULE.value:
            raise ValueError('Capsule authority is required for Capsule Tenant reconciliation.')


def require_capsule_capability(
    provider: CapsuleTenantProvider,
    *,
    cluster_id: str,
    capability: str,
) -> TenantProviderCapability:
    observed = {item.key: item for item in provider.capabilities(cluster_id=cluster_id)}
    selected = observed.get(capability)
    if selected is None or selected.status is not TenantCapabilityStatus.AVAILABLE:
        raise TenantProviderError(
            'capsule_capability_unavailable',
            f'Capsule Tenant capability {capability} is unavailable or degraded; operation fails closed.',
            capability=capability,
        )
    return selected


def validate_native_recovery_readiness(
    *,
    snapshot: CapsuleDiscoverySnapshot,
    native_capabilities: dict[str, TenantCapabilityStatus],
    materialized_capabilities: set[str],
    verified: bool,
) -> None:
    if not snapshot.installed:
        raise ValueError('Native Recovery requires a committed Capsule governance snapshot.')
    for capability in sorted(_RECOVERY_NATIVE_CAPABILITIES):
        if native_capabilities.get(capability) is not TenantCapabilityStatus.AVAILABLE:
            raise ValueError(f'Native Recovery requires available Native capability: {capability}.')
        if capability not in materialized_capabilities:
            raise ValueError(f'Native Recovery requires materialized Native protection: {capability}.')
    if not verified:
        raise ValueError('Native Recovery authority transfer requires verified effective enforcement.')
