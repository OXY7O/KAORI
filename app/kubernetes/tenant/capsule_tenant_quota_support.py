from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import InvalidOperation
from typing import Any

from kubernetes.utils.quantity import parse_quantity

from app.extensions.db import db
from app.kubernetes.tenant.capsule_tenant_quota_contract import (
    _AUTHORITY,
    _CAPABILITY,
    _CONTROL_DRIFTED,
    _CONTROL_MANAGED,
)
from app.kubernetes.tenant.service import (
    _namespace_allocation_values,
    resource_profile_attachment_controls,
)
from app.kubernetes.tenant.validation import COUNT_QUOTA_KEYS, SUPPORTED_QUOTA_KEYS
from app.models.tenant import Tenant, TenantResourceProfile


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


def _desired_resource_quotas(
    current: Mapping[str, Any],
    proposed_quota: Mapping[str, object],
    *,
    scope: str,
) -> dict[str, Any]:
    desired = deepcopy(dict(current))
    desired['scope'] = scope
    raw_items = desired.get('items')
    items = (
        [deepcopy(dict(item)) for item in raw_items if isinstance(item, Mapping)] if isinstance(raw_items, list) else []
    )
    if not items:
        items = [{'hard': {}}]

    owner_index: dict[str, int] = {}
    for index, item in enumerate(items):
        hard = item.get('hard')
        hard = dict(hard) if isinstance(hard, Mapping) else {}
        for key in hard:
            if key in SUPPORTED_QUOTA_KEYS and key not in owner_index:
                owner_index[str(key)] = index
        item['hard'] = {str(key): str(value) for key, value in hard.items() if key not in SUPPORTED_QUOTA_KEYS}

    for key, value in proposed_quota.items():
        index = owner_index.get(str(key), 0)
        hard = items[index].get('hard')
        hard = dict(hard) if isinstance(hard, Mapping) else {}
        hard[str(key)] = str(value)
        items[index]['hard'] = hard

    desired['items'] = items
    return desired


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


@dataclass(frozen=True, slots=True)
class _GovernanceCommitContext:
    profile: TenantResourceProfile
    desired_resource_quotas: Mapping[str, Any]
    effective_resource_quotas: Mapping[str, Any]
    desired_quota: Mapping[str, object]
    effective_quota: Mapping[str, object]
    scope: str
    source: Mapping[str, str]
    capacity_decision_id: int
    external_constraints: list[str]
    namespace_count: int
    provenance: str
    provider_mutation_performed: bool
    history: list[dict[str, Any]] | None = None


def _commit_governance(tenant: Tenant, context: _GovernanceCommitContext) -> None:
    evidence = _tenant_evidence(tenant)
    governance = {
        'authority': _AUTHORITY,
        'capability': _CAPABILITY,
        'control_state': _CONTROL_MANAGED,
        'allocation_scope': _allocation_scope(context.scope),
        'scope': context.scope,
        'resource_profile_id': context.profile.public_id,
        'resource_profile_version': context.profile.version,
        'allocation_customized': not _profile_matches_quota(context.profile, context.effective_quota),
        'capacity_decision_id': context.capacity_decision_id,
        'desired_resource_quotas': deepcopy(dict(context.desired_resource_quotas)),
        'effective_resource_quotas': deepcopy(dict(context.effective_resource_quotas)),
        'desired_quota': {str(key): str(value) for key, value in context.desired_quota.items()},
        'effective_quota': {str(key): str(value) for key, value in context.effective_quota.items()},
        'desired_hash': _canonical_hash(context.desired_resource_quotas),
        'effective_hash': _canonical_hash(context.effective_resource_quotas),
        'provider_source': dict(context.source),
        'external_constraints': list(context.external_constraints),
        'correlated_namespace_count': context.namespace_count,
        'provenance': context.provenance,
        'advanced_profile_controls': resource_profile_attachment_controls(context.profile, tenant),
        'history': list(context.history or []),
        'updated_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': context.provider_mutation_performed,
        'secret_material_persisted': False,
    }
    evidence['allocation_governance'] = governance
    evidence['allocation_control_state'] = _CONTROL_MANAGED
    evidence['resource_version'] = context.source.get('resource_version')
    evidence['provider_uid'] = context.source.get('uid') or evidence.get('provider_uid')
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
