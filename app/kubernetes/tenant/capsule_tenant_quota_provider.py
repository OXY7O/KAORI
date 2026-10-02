from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_observation import (
    observe_capsule_tenant_allocation,
    observe_capsule_tenant_resource_quota,
)
from app.kubernetes.tenant.capsule_provider import (
    CapsuleTenantProvider,
    discover_capsule,
    require_capsule_capability,
)
from app.kubernetes.tenant.capsule_tenant_quota_contract import (
    _AUTHORITY,
    _CAPABILITY,
    _CAPSULE_GROUP,
    _CAPSULE_PLURAL,
)
from app.kubernetes.tenant.capsule_tenant_quota_support import (
    _canonical_hash,
    _provider_source,
    _quota_contract_from_observation,
    _quota_differences,
    _resource_quota_authority_context,
    _resource_quotas,
    _tenant_evidence,
)
from app.kubernetes.tenant.providers import TenantProviderState
from app.kubernetes.tenant.validation import validate_profile_spec
from app.models import Cluster
from app.models.tenant import Tenant


def _cluster_client(tenant: Tenant):
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')
    return cluster, runtime_adapter.build_client(cluster)


def _read_live_tenant(
    tenant: Tenant,
    *,
    expected_source: Mapping[str, Any],
    require_resource_version_match: bool,
) -> tuple[dict[str, Any], dict[str, str], Any]:
    _cluster, client = _cluster_client(tenant)
    api = client.custom_objects_api()
    name = str(expected_source.get('name') or tenant.provider_reference or '').strip()
    api_version = str(
        expected_source.get('api_version') or _tenant_evidence(tenant).get('provider_api_version') or ''
    ).strip()
    if not name or not api_version:
        raise ValueError('Committed Capsule Tenant provider identity is incomplete.')

    try:
        item = api.get_cluster_custom_object(
            _CAPSULE_GROUP,
            api_version,
            _CAPSULE_PLURAL,
            name,
            _request_timeout=5,
        )
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError('Authoritative Capsule Tenant CR is no longer present.') from exc
        raise
    if not isinstance(item, dict):
        raise ValueError('Capsule Tenant provider response is invalid.')

    source = _provider_source(item, api_version=api_version)
    expected_uid = str(expected_source.get('uid') or '')
    expected_rv = str(expected_source.get('resource_version') or '')
    if expected_uid and source['uid'] and expected_uid != source['uid']:
        raise ValueError('Capsule Tenant UID changed; refresh provider evidence before mutation.')
    if (
        require_resource_version_match
        and expected_rv
        and source['resource_version']
        and expected_rv != source['resource_version']
    ):
        raise ValueError('Capsule Tenant resourceVersion changed; run Tenant Sync and review current provider state.')
    return item, source, client


def _prove_mutation_capability(
    tenant: Tenant,
    *,
    item: Mapping[str, Any],
    source: Mapping[str, str],
    client: Any,
) -> None:
    if tenant.provider_state != TenantProviderState.CAPSULE.value:
        raise ValueError('Capsule provider is degraded or unavailable.')
    api_version = source['api_version']
    resource_quotas = _resource_quotas(item)
    if not resource_quotas:
        raise ValueError('Capsule Tenant resourceQuotas are no longer present.')

    api = client.custom_objects_api()
    try:
        api.patch_cluster_custom_object(
            _CAPSULE_GROUP,
            api_version,
            _CAPSULE_PLURAL,
            source['name'],
            {
                'metadata': {
                    'name': source['name'],
                    'resourceVersion': source['resource_version'],
                },
                'spec': {'resourceQuotas': resource_quotas},
            },
            dry_run='All',
            _request_timeout=5,
        )
        snapshot = discover_capsule(
            api.api_client,
            probes={'admission_enforcement': True},
        )
        provider = CapsuleTenantProvider(snapshot=snapshot)
        binding = provider.validate_binding(cluster_id=str(tenant.cluster_id))
        if binding.state is not TenantProviderState.CAPSULE:
            raise ValueError('Capsule Tenant quota mutation is unavailable while provider authority is degraded.')
        require_capsule_capability(
            provider,
            cluster_id=str(tenant.cluster_id),
            capability=_CAPABILITY,
        )
    except ApiException as exc:
        raise ValueError(f'Capsule Tenant quota mutation preflight failed: {str(exc)[:700]}') from exc


def _prove_read_capability(tenant: Tenant, *, client: Any) -> None:
    if tenant.provider_state != TenantProviderState.CAPSULE.value:
        raise ValueError('Capsule provider is degraded or unavailable.')
    snapshot = discover_capsule(client.custom_objects_api().api_client)
    status = snapshot.capabilities.get(_CAPABILITY)
    status_value = str(getattr(status, 'value', status) or '')
    if status_value != 'available':
        raise ValueError('Capsule tenant_resource_quotas capability is unavailable in the live served CRD schema.')


def _live_allocation(
    tenant: Tenant,
    *,
    item: Mapping[str, Any],
    client: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    allocation = observe_capsule_tenant_allocation(
        client,
        tenant_name=str(tenant.provider_reference or tenant.slug),
        tenant_item=item,
    )
    if allocation.get('allocation_authority') != _AUTHORITY:
        raise ValueError(
            'Capsule allocation authority changed; Tenant.spec.resourceQuotas is no longer the single authoritative path.'
        )
    blockers = list(allocation.get('authority_unsupported_dimensions') or []) + list(
        allocation.get('authority_ambiguous_dimensions') or []
    )
    if blockers:
        raise ValueError('Capsule Tenant quota authority requires review: ' + '; '.join(str(item) for item in blockers))
    tenant_quota = allocation.get('tenant_resource_quota')
    if not isinstance(tenant_quota, Mapping):
        raise ValueError('Capsule Tenant resource quota observation is unavailable.')
    scope = str(tenant_quota.get('scope') or 'Tenant')
    if scope not in {'Tenant', 'Namespace'}:
        raise ValueError('Capsule Tenant resource quota scope is unsupported.')
    quota = tenant_quota.get('quota')
    if not isinstance(quota, Mapping):
        raise ValueError('Capsule Tenant resource quota values are unavailable.')
    validate_profile_spec(dict(quota), {})
    return dict(tenant_quota), allocation


def _patch_resource_quotas(
    tenant: Tenant,
    *,
    current_source: Mapping[str, str],
    desired_resource_quotas: Mapping[str, Any],
    client: Any,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    api = client.custom_objects_api()
    api.patch_cluster_custom_object(
        _CAPSULE_GROUP,
        current_source['api_version'],
        _CAPSULE_PLURAL,
        current_source['name'],
        {
            'metadata': {
                'name': current_source['name'],
                'resourceVersion': current_source['resource_version'],
            },
            'spec': {'resourceQuotas': deepcopy(dict(desired_resource_quotas))},
        },
        _request_timeout=5,
    )
    verified = api.get_cluster_custom_object(
        _CAPSULE_GROUP,
        current_source['api_version'],
        _CAPSULE_PLURAL,
        current_source['name'],
        _request_timeout=5,
    )
    if not isinstance(verified, dict):
        raise ValueError('Capsule Tenant read-back response is invalid.')
    verified_source = _provider_source(verified, api_version=current_source['api_version'])
    verified_quota = observe_capsule_tenant_resource_quota(verified)
    if not isinstance(verified_quota, Mapping):
        raise ValueError('Capsule Tenant read-back does not contain resourceQuotas.')
    return verified, verified_source, dict(verified_quota)


def _verify_effective(
    *,
    desired_resource_quotas: Mapping[str, Any],
    desired_quota: Mapping[str, object],
    desired_scope: str,
    verified_quota: Mapping[str, Any],
) -> None:
    observed_quota = verified_quota.get('quota')
    observed_scope = str(verified_quota.get('scope') or 'Tenant')
    if not isinstance(observed_quota, Mapping):
        raise ValueError('Capsule Tenant read-back quota values are unavailable.')
    differences = _quota_differences(desired_quota, observed_quota)
    if observed_scope != desired_scope or differences:
        raise ValueError('Capsule Tenant provider read-back does not match the proposed governed allocation.')
    if verified_quota.get('unsupported_dimensions') or verified_quota.get('ambiguous_dimensions'):
        raise ValueError('Capsule Tenant read-back contains unsupported or ambiguous quota semantics.')
    if _canonical_hash(_resource_quota_authority_context(desired_resource_quotas)) != _canonical_hash(
        _resource_quota_authority_context(_quota_contract_from_observation(verified_quota))
    ):
        raise ValueError('Capsule Tenant read-back changed non-hard resourceQuotas authority fields.')
