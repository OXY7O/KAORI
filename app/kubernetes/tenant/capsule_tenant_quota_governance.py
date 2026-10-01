from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from decimal import InvalidOperation
from typing import Any

from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.common.pagination import paginate_sequence
from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_observation import (
    observe_capsule_tenant_allocation,
    observe_capsule_tenant_resource_quota,
)
from app.kubernetes.tenant.capacity_governance import enforce_capsule_tenant_resource_quota_preflight
from app.kubernetes.tenant.capsule_provider import (
    CapsuleTenantProvider,
    discover_capsule,
    require_capsule_capability,
)
from app.kubernetes.tenant.providers import TenantProviderState
from app.kubernetes.tenant.service import (
    _namespace_allocation_values,
    _validate_resource_profile_attachment_controls,
    resource_profile_attachment_controls,
)
from app.kubernetes.tenant.validation import COUNT_QUOTA_KEYS, SUPPORTED_QUOTA_KEYS, validate_profile_spec
from app.models import Cluster
from app.models.tenant import (
    Tenant,
    TenantLifecycleStatus,
    TenantResourceProfile,
)

_CAPSULE_GROUP = 'capsule.clastix.io'
_CAPSULE_PLURAL = 'tenants'
_AUTHORITY = 'capsule_tenant_resource_quotas'
_CAPABILITY = 'tenant_resource_quotas'
_CONTROL_MANAGED = 'kaori_managed'
_CONTROL_DRIFTED = 'drifted'


class CapsuleTenantQuotaStateConflictError(RuntimeError):
    """Committed Capsule Tenant quota governance changed while applying an action."""


def _canonical_hash(payload: object) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _tenant_evidence(tenant: Tenant) -> dict[str, Any]:
    return deepcopy(tenant.provider_evidence_json or {})


def _allocation_baseline(tenant: Tenant) -> dict[str, Any]:
    baseline = _tenant_evidence(tenant).get('allocation_baseline')
    return dict(baseline) if isinstance(baseline, Mapping) else {}


def _governance(tenant: Tenant) -> dict[str, Any]:
    value = _tenant_evidence(tenant).get('allocation_governance')
    return dict(value) if isinstance(value, Mapping) else {}


def _capsule_capability_state(tenant: Tenant, capability: str) -> str:
    capsule = _tenant_evidence(tenant).get('capsule')
    capabilities = capsule.get('capabilities') if isinstance(capsule, Mapping) else None
    return str(capabilities.get(capability) or '') if isinstance(capabilities, Mapping) else ''


def _provider_source(item: Mapping[str, Any], *, api_version: str) -> dict[str, str]:
    metadata = item.get('metadata') if isinstance(item, Mapping) else {}
    metadata = metadata if isinstance(metadata, Mapping) else {}
    return {
        'kind': 'Tenant',
        'name': str(metadata.get('name') or ''),
        'uid': str(metadata.get('uid') or ''),
        'resource_version': str(metadata.get('resourceVersion') or ''),
        'api_version': api_version,
    }


def _resource_quotas(item: Mapping[str, Any]) -> dict[str, Any]:
    spec = item.get('spec') if isinstance(item, Mapping) else {}
    spec = spec if isinstance(spec, Mapping) else {}
    value = spec.get('resourceQuotas')
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _quota_for_profile(profile: TenantResourceProfile) -> dict[str, str]:
    quota, _limits, _storage_policy, _customized = _namespace_allocation_values(profile)
    return quota


def _quantity_equal(key: str, left: object, right: object) -> bool:
    left_text = str(left)
    right_text = str(right)
    if key in COUNT_QUOTA_KEYS:
        try:
            return int(left_text) == int(right_text)
        except (TypeError, ValueError):
            return False
    try:
        return parse_quantity(left_text) == parse_quantity(right_text)
    except (InvalidOperation, TypeError, ValueError):
        return left_text == right_text


def _quota_differences(
    desired: Mapping[str, object],
    observed: Mapping[str, object],
) -> list[dict[str, str]]:
    differences: list[dict[str, str]] = []
    for key in sorted(set(desired) | set(observed)):
        desired_value = desired.get(key)
        observed_value = observed.get(key)
        if desired_value is None or observed_value is None:
            if desired_value != observed_value:
                differences.append(
                    {
                        'dimension': key,
                        'kaori_value': str(desired_value) if desired_value is not None else 'Unbounded',
                        'provider_value': str(observed_value) if observed_value is not None else 'Unbounded',
                    }
                )
            continue
        if not _quantity_equal(key, desired_value, observed_value):
            differences.append(
                {
                    'dimension': key,
                    'kaori_value': str(desired_value),
                    'provider_value': str(observed_value),
                }
            )
    return differences


def _profile_matches_quota(profile: TenantResourceProfile, quota: Mapping[str, object]) -> bool:
    return not _quota_differences(_quota_for_profile(profile), quota)


def _managed_state(tenant: Tenant) -> bool:
    governance = _governance(tenant)
    return governance.get('authority') == _AUTHORITY and governance.get('control_state') in {
        _CONTROL_MANAGED,
        _CONTROL_DRIFTED,
    }


def _baseline_tenant_quota(tenant: Tenant) -> dict[str, Any]:
    value = _allocation_baseline(tenant).get('tenant_resource_quota')
    return dict(value) if isinstance(value, Mapping) else {}


def _baseline_source(tenant: Tenant) -> dict[str, str]:
    evidence = _tenant_evidence(tenant)
    return {
        'kind': 'Tenant',
        'name': str(evidence.get('resource_name') or tenant.provider_reference or tenant.slug),
        'uid': str(evidence.get('provider_uid') or ''),
        'resource_version': str(evidence.get('resource_version') or ''),
        'api_version': str(evidence.get('provider_api_version') or ''),
    }


def build_capsule_tenant_quota_cutover_state(tenant: Tenant) -> dict[str, Any]:
    baseline = _allocation_baseline(tenant)
    tenant_quota = _baseline_tenant_quota(tenant)
    reasons: list[str] = []

    if tenant.provider_key != 'capsule' or tenant.reconciliation_authority != 'capsule':
        reasons.append('Capsule reconciliation authority is required.')
    if tenant.provider_state != TenantProviderState.CAPSULE.value:
        reasons.append('Capsule provider is degraded or unavailable.')
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        reasons.append('Tenant is not Ready; allocation governance is frozen during teardown.')
    if baseline.get('allocation_authority') != _AUTHORITY:
        reasons.append('Effective allocation authority is not Capsule Tenant.spec.resourceQuotas.')
    if _capsule_capability_state(tenant, _CAPABILITY) != 'available':
        reasons.append('Capsule tenant_resource_quotas capability is unavailable or degraded.')

    authority_unsupported = list(baseline.get('authority_unsupported_dimensions') or [])
    authority_ambiguous = list(baseline.get('authority_ambiguous_dimensions') or [])
    if authority_unsupported:
        reasons.append('Authoritative Tenant resource quota contains unsupported dimensions.')
    if authority_ambiguous:
        reasons.append('Authoritative Tenant resource quota is ambiguous.')

    quota = tenant_quota.get('quota')
    scope = str(tenant_quota.get('scope') or 'Tenant')
    items = tenant_quota.get('items')
    if not isinstance(quota, Mapping):
        reasons.append('Observed Tenant resource quota values are unavailable.')
    if scope not in {'Tenant', 'Namespace'}:
        reasons.append('Capsule Tenant resource quota scope is unsupported.')
    if not isinstance(items, list) or not items:
        reasons.append('Observed Tenant resource quota item structure is unavailable.')

    source = _baseline_source(tenant)
    if not source['name'] or not source['uid'] or not source['resource_version'] or not source['api_version']:
        reasons.append('Committed Capsule Tenant provider identity is incomplete.')

    governance = _governance(tenant)
    if governance.get('authority') == _AUTHORITY and governance.get('control_state') in {
        _CONTROL_MANAGED,
        _CONTROL_DRIFTED,
    }:
        reasons.append('Tenant resource quota is already governed by KAORI.')

    return {
        'supported': not reasons,
        'state': 'adopted_observed' if not reasons else 'control_unavailable',
        'reason': (
            'Eligible for explicit Capsule Tenant quota governance cutover.'
            if not reasons
            else ' '.join(dict.fromkeys(reasons))
        ),
        'authority': str(baseline.get('allocation_authority') or 'unknown'),
        'current_quota': dict(quota) if isinstance(quota, Mapping) else {},
        'scope': scope,
        'source': source,
        'external_constraints': list(baseline.get('external_constraints') or []),
        'correlated_namespace_count': len(list(baseline.get('correlated_namespaces') or [])),
    }


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
        expected_source.get('api_version')
        or _tenant_evidence(tenant).get('provider_api_version')
        or ''
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


def _desired_resource_quotas(
    current: Mapping[str, Any],
    proposed_quota: Mapping[str, object],
    *,
    scope: str,
) -> dict[str, Any]:
    desired = deepcopy(dict(current))
    desired['scope'] = scope
    raw_items = desired.get('items')
    items = [deepcopy(dict(item)) for item in raw_items if isinstance(item, Mapping)] if isinstance(raw_items, list) else []
    if not items:
        items = [{'hard': {}}]

    owner_index: dict[str, int] = {}
    for index, item in enumerate(items):
        hard = item.get('hard')
        hard = dict(hard) if isinstance(hard, Mapping) else {}
        for key in hard:
            if key in SUPPORTED_QUOTA_KEYS and key not in owner_index:
                owner_index[str(key)] = index
        item['hard'] = {
            str(key): str(value)
            for key, value in hard.items()
            if key not in SUPPORTED_QUOTA_KEYS
        }

    for key, value in proposed_quota.items():
        index = owner_index.get(str(key), 0)
        hard = items[index].get('hard')
        hard = dict(hard) if isinstance(hard, Mapping) else {}
        hard[str(key)] = str(value)
        items[index]['hard'] = hard

    desired['items'] = items
    return desired


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


def _quota_contract_from_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'scope': str(observation.get('scope') or 'Tenant'),
        'items': deepcopy(list(observation.get('items') or [])),
    }


def _resource_quota_authority_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = deepcopy(dict(payload))
    items = context.get('items')
    normalized_items: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, Mapping):
            continue
        copy = deepcopy(dict(item))
        copy.pop('hard', None)
        normalized_items.append(copy)
    context['items'] = normalized_items
    return context


def _allocation_scope(scope: str) -> str:
    return 'tenant_shared' if scope == 'Tenant' else 'tenant_namespace_template'


def _namespace_count(allocation: Mapping[str, Any]) -> int:
    return len(list(allocation.get('correlated_namespaces') or []))


def _commit_governance(
    tenant: Tenant,
    *,
    profile: TenantResourceProfile,
    desired_resource_quotas: Mapping[str, Any],
    effective_resource_quotas: Mapping[str, Any],
    desired_quota: Mapping[str, object],
    effective_quota: Mapping[str, object],
    scope: str,
    source: Mapping[str, str],
    capacity_decision_id: int,
    external_constraints: list[str],
    namespace_count: int,
    provenance: str,
    provider_mutation_performed: bool,
    history: list[dict[str, Any]] | None = None,
) -> None:
    evidence = _tenant_evidence(tenant)
    governance = {
        'authority': _AUTHORITY,
        'capability': _CAPABILITY,
        'control_state': _CONTROL_MANAGED,
        'allocation_scope': _allocation_scope(scope),
        'scope': scope,
        'resource_profile_id': profile.public_id,
        'resource_profile_version': profile.version,
        'allocation_customized': not _profile_matches_quota(profile, effective_quota),
        'capacity_decision_id': capacity_decision_id,
        'desired_resource_quotas': deepcopy(dict(desired_resource_quotas)),
        'effective_resource_quotas': deepcopy(dict(effective_resource_quotas)),
        'desired_quota': {str(key): str(value) for key, value in desired_quota.items()},
        'effective_quota': {str(key): str(value) for key, value in effective_quota.items()},
        'desired_hash': _canonical_hash(desired_resource_quotas),
        'effective_hash': _canonical_hash(effective_resource_quotas),
        'provider_source': dict(source),
        'external_constraints': list(external_constraints),
        'correlated_namespace_count': namespace_count,
        'provenance': provenance,
        'advanced_profile_controls': resource_profile_attachment_controls(profile, tenant),
        'history': list(history or []),
        'updated_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': provider_mutation_performed,
        'secret_material_persisted': False,
    }
    evidence['allocation_governance'] = governance
    evidence['allocation_control_state'] = _CONTROL_MANAGED
    evidence['resource_version'] = source.get('resource_version')
    evidence['provider_uid'] = source.get('uid') or evidence.get('provider_uid')
    tenant.provider_evidence_json = evidence


def _record_failure(
    tenant: Tenant,
    *,
    operation: str,
    error: Exception,
    provider_mutation_may_have_started: bool,
) -> None:
    evidence = _tenant_evidence(tenant)
    evidence['allocation_governance_failure'] = {
        'authority': _AUTHORITY,
        'operation': operation,
        'at': datetime.now(UTC).isoformat(),
        'error': str(error)[:1000],
        'provider_mutation_may_have_started': provider_mutation_may_have_started,
        'secret_material_persisted': False,
    }
    tenant.provider_evidence_json = evidence


def _profile(profile_id: int) -> TenantResourceProfile:
    profile = db.session.get(TenantResourceProfile, profile_id)
    if profile is None or not profile.enabled:
        raise ValueError('Selected Resource Profile is unavailable.')
    return profile


def _lineage_profile(tenant: Tenant) -> TenantResourceProfile:
    profile_public_id = _governance(tenant).get('resource_profile_id')
    profile = TenantResourceProfile.query.filter_by(public_id=profile_public_id).first()
    if profile is None or not profile.enabled:
        raise ValueError('Committed Resource Profile lineage is unavailable for Capsule Tenant quota reconciliation.')
    return profile


def cutover_capsule_tenant_resource_quota(
    *,
    tenant_id: str,
    profile_id: int,
) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')
    profile = _profile(profile_id)
    _validate_resource_profile_attachment_controls(profile, tenant)
    state = build_capsule_tenant_quota_cutover_state(tenant)
    if not state['supported']:
        raise ValueError(str(state['reason']))

    provider_mutation_started = False
    try:
        item, source, client = _read_live_tenant(
            tenant,
            expected_source=state['source'],
            require_resource_version_match=True,
        )
        _prove_mutation_capability(tenant, item=item, source=source, client=client)
        current_tenant_quota, allocation = _live_allocation(tenant, item=item, client=client)
        current_quota = dict(current_tenant_quota.get('quota') or {})
        scope = str(current_tenant_quota.get('scope') or 'Tenant')
        proposed_quota = _quota_for_profile(profile)
        capacity = enforce_capsule_tenant_resource_quota_preflight(
            tenant=tenant,
            profile=profile,
            current_quota_hard=current_quota,
            proposed_quota_hard=proposed_quota,
            current_scope=scope,
            proposed_scope=scope,
            namespace_count=_namespace_count(allocation),
        )
        desired_resource_quotas = _desired_resource_quotas(
            _resource_quotas(item),
            proposed_quota,
            scope=scope,
        )
        provider_mutation_started = True
        _verified, verified_source, verified_quota = _patch_resource_quotas(
            tenant,
            current_source=source,
            desired_resource_quotas=desired_resource_quotas,
            client=client,
        )
        _verify_effective(
            desired_resource_quotas=desired_resource_quotas,
            desired_quota=proposed_quota,
            desired_scope=scope,
            verified_quota=verified_quota,
        )
        effective_quota = dict(verified_quota.get('quota') or {})
        effective_resource_quotas = _quota_contract_from_observation(verified_quota)
        _commit_governance(
            tenant,
            profile=profile,
            desired_resource_quotas=desired_resource_quotas,
            effective_resource_quotas=effective_resource_quotas,
            desired_quota=proposed_quota,
            effective_quota=effective_quota,
            scope=scope,
            source=verified_source,
            capacity_decision_id=capacity.id,
            external_constraints=list(allocation.get('external_constraints') or []),
            namespace_count=_namespace_count(allocation),
            provenance='kaori_managed',
            provider_mutation_performed=True,
            history=[
                {
                    'event': 'allocation_governance_cutover',
                    'at': datetime.now(UTC).isoformat(),
                    'observed_before': current_quota,
                    'desired_after': proposed_quota,
                }
            ],
        )
        return tenant
    except (ApiException, ValueError) as exc:
        _record_failure(
            tenant,
            operation='allocation_governance_cutover',
            error=exc,
            provider_mutation_may_have_started=provider_mutation_started,
        )
        raise


def cutover_capsule_tenant_resource_quota_committed(
    *,
    tenant_id: str,
    profile_id: int,
) -> Tenant:
    try:
        tenant = cutover_capsule_tenant_resource_quota(
            tenant_id=tenant_id,
            profile_id=profile_id,
        )
        db.session.commit()
        return tenant
    except IntegrityError as exc:
        db.session.rollback()
        raise CapsuleTenantQuotaStateConflictError(
            'Committed Capsule Tenant quota state changed during governance cutover. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def change_capsule_tenant_resource_quota(
    *,
    tenant_id: str,
    profile_id: int,
) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')
    if not _managed_state(tenant):
        raise ValueError('Capsule Tenant allocation must complete governance cutover before managed changes.')
    governance = _governance(tenant)
    if governance.get('control_state') != _CONTROL_MANAGED:
        raise ValueError('Drifted Capsule Tenant allocation must be reconciled before a new allocation change.')

    profile = _profile(profile_id)
    _validate_resource_profile_attachment_controls(profile, tenant)
    expected_source = governance.get('provider_source')
    expected_source = expected_source if isinstance(expected_source, Mapping) else {}
    provider_mutation_started = False
    try:
        item, source, client = _read_live_tenant(
            tenant,
            expected_source=expected_source,
            require_resource_version_match=True,
        )
        _prove_mutation_capability(tenant, item=item, source=source, client=client)
        current_tenant_quota, allocation = _live_allocation(tenant, item=item, client=client)
        current_quota = dict(current_tenant_quota.get('quota') or {})
        current_scope = str(current_tenant_quota.get('scope') or 'Tenant')
        proposed_scope = str(governance.get('scope') or current_scope)
        if current_scope != proposed_scope:
            raise ValueError('Capsule Tenant quota scope changed outside KAORI; run Tenant Sync before changing allocation.')
        proposed_quota = _quota_for_profile(profile)
        capacity = enforce_capsule_tenant_resource_quota_preflight(
            tenant=tenant,
            profile=profile,
            current_quota_hard=current_quota,
            proposed_quota_hard=proposed_quota,
            current_scope=current_scope,
            proposed_scope=proposed_scope,
            namespace_count=_namespace_count(allocation),
        )
        desired_resource_quotas = _desired_resource_quotas(
            _resource_quotas(item),
            proposed_quota,
            scope=proposed_scope,
        )
        provider_mutation_started = True
        _verified, verified_source, verified_quota = _patch_resource_quotas(
            tenant,
            current_source=source,
            desired_resource_quotas=desired_resource_quotas,
            client=client,
        )
        _verify_effective(
            desired_resource_quotas=desired_resource_quotas,
            desired_quota=proposed_quota,
            desired_scope=proposed_scope,
            verified_quota=verified_quota,
        )
        history = list(governance.get('history') or [])
        history.append(
            {
                'event': 'managed_allocation_change',
                'at': datetime.now(UTC).isoformat(),
                'desired_before': dict(governance.get('desired_quota') or {}),
                'desired_after': proposed_quota,
            }
        )
        _commit_governance(
            tenant,
            profile=profile,
            desired_resource_quotas=desired_resource_quotas,
            effective_resource_quotas=_quota_contract_from_observation(verified_quota),
            desired_quota=proposed_quota,
            effective_quota=dict(verified_quota.get('quota') or {}),
            scope=proposed_scope,
            source=verified_source,
            capacity_decision_id=capacity.id,
            external_constraints=list(allocation.get('external_constraints') or []),
            namespace_count=_namespace_count(allocation),
            provenance='kaori_managed',
            provider_mutation_performed=True,
            history=history,
        )
        return tenant
    except (ApiException, ValueError) as exc:
        _record_failure(
            tenant,
            operation='managed_allocation_change',
            error=exc,
            provider_mutation_may_have_started=provider_mutation_started,
        )
        raise


def change_capsule_tenant_resource_quota_committed(
    *,
    tenant_id: str,
    profile_id: int,
) -> Tenant:
    try:
        tenant = change_capsule_tenant_resource_quota(
            tenant_id=tenant_id,
            profile_id=profile_id,
        )
        db.session.commit()
        return tenant
    except IntegrityError as exc:
        db.session.rollback()
        raise CapsuleTenantQuotaStateConflictError(
            'Committed Capsule Tenant quota state changed during allocation update. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def observe_managed_capsule_tenant_quota(tenant: Tenant) -> dict[str, Any]:
    governance = _governance(tenant)
    if governance.get('authority') != _AUTHORITY:
        raise ValueError('Tenant is not governed through Capsule Tenant.spec.resourceQuotas.')
    expected_source = governance.get('provider_source')
    expected_source = expected_source if isinstance(expected_source, Mapping) else {}
    item, source, client = _read_live_tenant(
        tenant,
        expected_source=expected_source,
        require_resource_version_match=False,
    )
    desired_quota = dict(governance.get('desired_quota') or {})
    desired_scope = str(governance.get('scope') or 'Tenant')
    blocked_reasons: list[str] = []
    try:
        live_tenant_quota, allocation = _live_allocation(tenant, item=item, client=client)
        observed_quota = dict(live_tenant_quota.get('quota') or {})
        observed_scope = str(live_tenant_quota.get('scope') or 'Tenant')
        observed_resource_quotas = _resource_quotas(item)
        if observed_scope != desired_scope:
            blocked_reasons.append(
                f'Capsule Tenant quota scope changed from {desired_scope} to {observed_scope}.'
            )
        desired_resource_quotas = governance.get('desired_resource_quotas')
        desired_resource_quotas = (
            dict(desired_resource_quotas)
            if isinstance(desired_resource_quotas, Mapping)
            else {}
        )
        if _canonical_hash(_resource_quota_authority_context(desired_resource_quotas)) != _canonical_hash(
            _resource_quota_authority_context(observed_resource_quotas)
        ):
            blocked_reasons.append('Capsule Tenant resourceQuotas non-hard authority fields changed outside KAORI.')
        external_constraints = list(allocation.get('external_constraints') or [])
        namespace_count = _namespace_count(allocation)
    except ValueError as exc:
        observed = observe_capsule_tenant_resource_quota(item)
        observed_quota = dict(observed.get('quota') or {}) if isinstance(observed, Mapping) else {}
        observed_scope = str(observed.get('scope') or 'Tenant') if isinstance(observed, Mapping) else 'Tenant'
        observed_resource_quotas = _resource_quotas(item)
        external_constraints = list(governance.get('external_constraints') or [])
        namespace_count = int(governance.get('correlated_namespace_count') or 0)
        blocked_reasons.append(str(exc))

    differences = _quota_differences(desired_quota, observed_quota)
    return {
        'observed_at': datetime.now(UTC).isoformat(),
        'desired_quota': desired_quota,
        'observed_quota': observed_quota,
        'desired_scope': desired_scope,
        'observed_scope': observed_scope,
        'differences': differences,
        'blocked_reasons': blocked_reasons,
        'observed_matches_desired': not differences and not blocked_reasons,
        'observed_resource_quotas': observed_resource_quotas,
        'provider_source': source,
        'observed_hash': _canonical_hash(observed_resource_quotas),
        'external_constraints': external_constraints,
        'correlated_namespace_count': namespace_count,
        'provider_mutation_performed': False,
    }


def apply_managed_capsule_tenant_quota_drift_observation() -> dict[str, Any]:
    tenants = (
        Tenant.query.filter(
            Tenant.provider_key == 'capsule',
            Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value,
        )
        .order_by(Tenant.id.asc())
        .all()
    )
    drifted_tenant_ids: list[str] = []
    observation_errors: list[dict[str, Any]] = []
    for tenant in tenants:
        governance = _governance(tenant)
        if governance.get('authority') != _AUTHORITY or governance.get('control_state') not in {
            _CONTROL_MANAGED,
            _CONTROL_DRIFTED,
        }:
            continue
        evidence = _tenant_evidence(tenant)
        try:
            observation = observe_managed_capsule_tenant_quota(tenant)
        except (ApiException, ValueError) as exc:
            governance['control_state'] = _CONTROL_DRIFTED
            governance['allocation_drift'] = {
                'observed_at': datetime.now(UTC).isoformat(),
                'blocked_reasons': [str(exc)[:1000]],
                'provider_mutation_performed': False,
            }
            evidence['allocation_governance'] = governance
            evidence['allocation_control_state'] = _CONTROL_DRIFTED
            tenant.provider_evidence_json = evidence
            drifted_tenant_ids.append(tenant.id)
            observation_errors.append(
                {
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'reason': str(exc)[:1000],
                }
            )
            continue

        prior_drift = governance.get('control_state') == _CONTROL_DRIFTED and isinstance(
            governance.get('allocation_drift'),
            Mapping,
        )
        if observation['differences'] or observation['blocked_reasons'] or prior_drift:
            governance['control_state'] = _CONTROL_DRIFTED
            governance['allocation_drift'] = observation
            evidence['allocation_governance'] = governance
            evidence['allocation_control_state'] = _CONTROL_DRIFTED
            tenant.provider_evidence_json = evidence
            drifted_tenant_ids.append(tenant.id)

    return {
        'drifted_tenant_ids': sorted(set(drifted_tenant_ids)),
        'observation_errors': observation_errors,
    }


def build_capsule_tenant_quota_drift_action_state(tenant: Tenant) -> dict[str, Any]:
    governance = _governance(tenant)
    drift_value = governance.get('allocation_drift')
    drift = dict(drift_value) if isinstance(drift_value, Mapping) else {}
    reasons = list(drift.get('blocked_reasons') or [])
    if governance.get('authority') != _AUTHORITY:
        reasons.append('Tenant is not governed through Capsule Tenant.spec.resourceQuotas.')
    if governance.get('control_state') != _CONTROL_DRIFTED:
        reasons.append('Capsule Tenant quota reconciliation requires committed Drifted state.')
    if not isinstance(drift_value, Mapping):
        reasons.append('No committed Capsule Tenant quota drift evidence is available.')
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        reasons.append('Tenant is not Ready; reconciliation is frozen during teardown.')
    if tenant.provider_state != TenantProviderState.CAPSULE.value:
        reasons.append('Capsule provider is degraded or unavailable.')
    if _capsule_capability_state(tenant, _CAPABILITY) != 'available':
        reasons.append('Capsule tenant_resource_quotas capability is unavailable or degraded.')
    return {
        'reapply_supported': not reasons,
        'accept_supported': not reasons,
        'blocked_reason': ' '.join(dict.fromkeys(str(reason) for reason in reasons if reason)),
        'drift': drift,
        'authority': _AUTHORITY,
    }


def _fresh_drift_observation(
    tenant: Tenant,
    *,
    require_mutation_capability: bool = True,
) -> tuple[dict[str, Any], dict[str, str], Any, dict[str, Any], dict[str, Any]]:
    state = build_capsule_tenant_quota_drift_action_state(tenant)
    if not state['reapply_supported']:
        raise ValueError(str(state['blocked_reason']))
    drift = state['drift']
    source = drift.get('provider_source')
    source = source if isinstance(source, Mapping) else {}
    item, current_source, client = _read_live_tenant(
        tenant,
        expected_source=source,
        require_resource_version_match=True,
    )
    current_resource_quotas = _resource_quotas(item)
    expected_hash = str(drift.get('observed_hash') or '')
    if expected_hash and _canonical_hash(current_resource_quotas) != expected_hash:
        raise ValueError('Capsule provider state changed since drift observation; run Tenant Sync and review again.')
    if require_mutation_capability:
        _prove_mutation_capability(tenant, item=item, source=current_source, client=client)
    else:
        _prove_read_capability(tenant, client=client)
    live_tenant_quota, allocation = _live_allocation(tenant, item=item, client=client)
    return item, current_source, client, live_tenant_quota, allocation


def reapply_capsule_tenant_quota_intent(tenant: Tenant) -> Tenant:
    governance = _governance(tenant)
    _item, source, client, live_tenant_quota, allocation = _fresh_drift_observation(tenant)
    profile = _lineage_profile(tenant)
    desired_quota = dict(governance.get('desired_quota') or {})
    desired_resource_quotas = governance.get('desired_resource_quotas')
    desired_resource_quotas = (
        dict(desired_resource_quotas)
        if isinstance(desired_resource_quotas, Mapping)
        else {}
    )
    desired_scope = str(governance.get('scope') or 'Tenant')
    live_quota = dict(live_tenant_quota.get('quota') or {})
    live_scope = str(live_tenant_quota.get('scope') or 'Tenant')
    capacity = enforce_capsule_tenant_resource_quota_preflight(
        tenant=tenant,
        profile=profile,
        current_quota_hard=live_quota,
        proposed_quota_hard=desired_quota,
        current_scope=live_scope,
        proposed_scope=desired_scope,
        namespace_count=_namespace_count(allocation),
    )
    _verified, verified_source, verified_quota = _patch_resource_quotas(
        tenant,
        current_source=source,
        desired_resource_quotas=desired_resource_quotas,
        client=client,
    )
    _verify_effective(
        desired_resource_quotas=desired_resource_quotas,
        desired_quota=desired_quota,
        desired_scope=desired_scope,
        verified_quota=verified_quota,
    )
    history = list(governance.get('history') or [])
    history.append(
        {
            'event': 'reapply_kaori_intent',
            'at': datetime.now(UTC).isoformat(),
            'provider_before': live_quota,
            'desired_reapplied': desired_quota,
        }
    )
    _commit_governance(
        tenant,
        profile=profile,
        desired_resource_quotas=desired_resource_quotas,
        effective_resource_quotas=_quota_contract_from_observation(verified_quota),
        desired_quota=desired_quota,
        effective_quota=dict(verified_quota.get('quota') or {}),
        scope=desired_scope,
        source=verified_source,
        capacity_decision_id=capacity.id,
        external_constraints=list(allocation.get('external_constraints') or []),
        namespace_count=_namespace_count(allocation),
        provenance=str(governance.get('provenance') or 'kaori_managed'),
        provider_mutation_performed=True,
        history=history,
    )
    return tenant


def reapply_capsule_tenant_quota_intent_committed(*, tenant_id: str) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Capsule Tenant no longer exists.')
    try:
        result = reapply_capsule_tenant_quota_intent(tenant)
        db.session.commit()
        return result
    except IntegrityError as exc:
        db.session.rollback()
        raise CapsuleTenantQuotaStateConflictError(
            'Committed Capsule Tenant quota drift changed during Reapply KAORI Intent. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def accept_capsule_tenant_provider_state(tenant: Tenant) -> Tenant:
    governance = _governance(tenant)
    _item, source, _client, live_tenant_quota, allocation = _fresh_drift_observation(
        tenant,
        require_mutation_capability=False,
    )
    profile = _lineage_profile(tenant)
    committed_quota = dict(governance.get('desired_quota') or {})
    committed_scope = str(governance.get('scope') or 'Tenant')
    live_quota = dict(live_tenant_quota.get('quota') or {})
    live_scope = str(live_tenant_quota.get('scope') or 'Tenant')
    capacity = enforce_capsule_tenant_resource_quota_preflight(
        tenant=tenant,
        profile=profile,
        current_quota_hard=committed_quota,
        proposed_quota_hard=live_quota,
        current_scope=committed_scope,
        proposed_scope=live_scope,
        namespace_count=_namespace_count(allocation),
    )
    live_resource_quotas = _quota_contract_from_observation(live_tenant_quota)
    history = list(governance.get('history') or [])
    history.append(
        {
            'event': 'accept_provider_state',
            'at': datetime.now(UTC).isoformat(),
            'desired_before': committed_quota,
            'provider_accepted': live_quota,
            'provider_mutation_performed': False,
        }
    )
    _commit_governance(
        tenant,
        profile=profile,
        desired_resource_quotas=live_resource_quotas,
        effective_resource_quotas=live_resource_quotas,
        desired_quota=live_quota,
        effective_quota=live_quota,
        scope=live_scope,
        source=source,
        capacity_decision_id=capacity.id,
        external_constraints=list(allocation.get('external_constraints') or []),
        namespace_count=_namespace_count(allocation),
        provenance='accepted_provider_state',
        provider_mutation_performed=False,
        history=history,
    )
    return tenant


def accept_capsule_tenant_provider_state_committed(*, tenant_id: str) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Capsule Tenant no longer exists.')
    try:
        result = accept_capsule_tenant_provider_state(tenant)
        db.session.commit()
        return result
    except IntegrityError as exc:
        db.session.rollback()
        raise CapsuleTenantQuotaStateConflictError(
            'Committed Capsule Tenant quota drift changed during Accept Provider State. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def get_capsule_tenant_quota_context(
    *,
    drift_page: int = 1,
    drift_per_page: int = 5,
) -> dict[str, Any]:
    tenants = (
        Tenant.query.filter(
            Tenant.provider_key == 'capsule',
            Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value,
        )
        .order_by(Tenant.name.asc())
        .all()
    )
    cutover_state = {
        tenant.id: build_capsule_tenant_quota_cutover_state(tenant)
        for tenant in tenants
    }
    cutover_tenants = [
        tenant
        for tenant in tenants
        if cutover_state[tenant.id].get('authority') == _AUTHORITY
        and not _managed_state(tenant)
    ]
    blocked_cutover_tenants = [
        tenant
        for tenant in cutover_tenants
        if not bool(cutover_state[tenant.id].get('supported'))
    ]
    managed = [
        tenant
        for tenant in tenants
        if _governance(tenant).get('authority') == _AUTHORITY
        and _governance(tenant).get('control_state') == _CONTROL_MANAGED
    ]
    drifted = [
        tenant
        for tenant in tenants
        if _governance(tenant).get('authority') == _AUTHORITY
        and _governance(tenant).get('control_state') == _CONTROL_DRIFTED
    ]
    visible_drifted, pagination = paginate_sequence(
        drifted,
        page=drift_page,
        per_page=drift_per_page,
    )
    return {
        'capsule_tenant_quota_tenants': tenants,
        'capsule_tenant_quota_cutover_tenants': cutover_tenants,
        'capsule_tenant_quota_blocked_cutover_tenants': blocked_cutover_tenants,
        'capsule_tenant_quota_cutover_state': cutover_state,
        'capsule_tenant_quota_cutover_supported': any(
            item['supported'] for item in cutover_state.values()
        ),
        'capsule_tenant_quota_managed': managed,
        'capsule_tenant_quota_drifted': visible_drifted,
        'capsule_tenant_quota_drift_pagination': pagination,
        'capsule_tenant_quota_drift_state': {
            tenant.id: build_capsule_tenant_quota_drift_action_state(tenant)
            for tenant in visible_drifted
        },
        'capsule_tenant_quota_governance': {
            tenant.id: _governance(tenant)
            for tenant in tenants
            if _governance(tenant).get('authority') == _AUTHORITY
        },
    }
