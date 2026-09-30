from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.common.pagination import paginate_sequence
from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_cutover import _quantity_equal
from app.kubernetes.tenant.capacity_governance import enforce_shared_tenant_allocation_preflight
from app.kubernetes.tenant.capsule_advanced import reconcile_capsule_advanced_intent
from app.kubernetes.tenant.capsule_advanced_service import _provider_from_committed_evidence
from app.kubernetes.tenant.service import _namespace_allocation_values
from app.models import Cluster
from app.models.tenant import (
    Tenant,
    TenantLifecycleStatus,
    TenantResourceProfile,
)
from app.models.tenant_advanced import (
    TenantAdvancedCapabilityIntent,
    TenantAdvancedCapabilityStatus,
)

_CAPSULE_GROUP = 'capsule.clastix.io'
_GLOBAL_QUOTA_PLURAL = 'globalresourcequotas'
_REQUIRED_API_VERSION = 'v1beta2'
_SHARED_CAPABILITY = 'shared_global_quota'
_SHARED_SCOPE = 'tenant_shared'


class CapsuleSharedAllocationStateConflictError(RuntimeError):
    """Committed shared allocation state changed while provider mutation was applying."""


def _canonical_hash(payload: object) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _tenant_evidence(tenant: Tenant) -> dict[str, Any]:
    return deepcopy(tenant.provider_evidence_json or {})


def _allocation_baseline(tenant: Tenant) -> dict[str, Any]:
    baseline = _tenant_evidence(tenant).get('allocation_baseline')
    return dict(baseline) if isinstance(baseline, Mapping) else {}


def _capsule_capability_state(tenant: Tenant, capability: str) -> str:
    capsule = _tenant_evidence(tenant).get('capsule')
    capabilities = capsule.get('capabilities') if isinstance(capsule, Mapping) else None
    return str(capabilities.get(capability) or '') if isinstance(capabilities, Mapping) else ''


def _source_reference(payload: Mapping[str, Any]) -> dict[str, str]:
    metadata = payload.get('metadata') if isinstance(payload, Mapping) else {}
    metadata = metadata if isinstance(metadata, Mapping) else {}
    return {
        'kind': 'GlobalResourceQuota',
        'name': str(metadata.get('name') or ''),
        'uid': str(metadata.get('uid') or ''),
        'resource_version': str(metadata.get('resourceVersion') or ''),
    }


def _quota_from_global_resource(payload: Mapping[str, Any]) -> dict[str, str]:
    spec = payload.get('spec') if isinstance(payload, Mapping) else {}
    spec = spec if isinstance(spec, Mapping) else {}
    quota = spec.get('quota')
    quota = quota if isinstance(quota, Mapping) else {}
    hard = quota.get('hard')
    return {str(key): str(value) for key, value in dict(hard or {}).items()} if isinstance(hard, Mapping) else {}


def _desired_shared_spec(current: Mapping[str, Any], quota_hard: Mapping[str, object]) -> dict[str, Any]:
    spec = current.get('spec') if isinstance(current, Mapping) else {}
    desired = deepcopy(dict(spec)) if isinstance(spec, Mapping) else {}
    quota = desired.get('quota')
    quota = deepcopy(dict(quota)) if isinstance(quota, Mapping) else {}
    quota['hard'] = {str(key): str(value) for key, value in quota_hard.items()}
    desired['quota'] = quota
    return desired


def _active_shared_intents(tenant_id: str) -> list[TenantAdvancedCapabilityIntent]:
    return (
        TenantAdvancedCapabilityIntent.query.filter(
            TenantAdvancedCapabilityIntent.tenant_id == tenant_id,
            TenantAdvancedCapabilityIntent.resource_kind == 'global_resource_quota',
            TenantAdvancedCapabilityIntent.status != TenantAdvancedCapabilityStatus.DISABLED.value,
        )
        .order_by(TenantAdvancedCapabilityIntent.updated_at.desc())
        .all()
    )


def _managed_shared_intent(tenant: Tenant) -> TenantAdvancedCapabilityIntent | None:
    matches = [
        intent
        for intent in _active_shared_intents(tenant.id)
        if (intent.reconciliation_evidence_json or {}).get('allocation_governance_scope') == _SHARED_SCOPE
    ]
    if len(matches) > 1:
        raise ValueError('Multiple canonical shared allocation intents exist for this Tenant; reconciliation fails closed.')
    return matches[0] if matches else None


def build_capsule_shared_allocation_cutover_state(tenant: Tenant) -> dict[str, Any]:
    baseline = _allocation_baseline(tenant)
    global_quota = baseline.get('global_resource_quota')
    global_quota = dict(global_quota) if isinstance(global_quota, Mapping) else {}
    sources = [
        dict(item)
        for item in list(global_quota.get('source_resources') or [])
        if isinstance(item, Mapping)
    ]
    reasons: list[str] = []

    if tenant.provider_key != 'capsule' or tenant.reconciliation_authority != 'capsule':
        reasons.append('Capsule reconciliation authority is required.')
    if tenant.provider_state != 'capsule':
        reasons.append('Capsule provider is not healthy; shared allocation mutation fails closed.')
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        reasons.append('Tenant is not Ready; allocation governance is frozen during teardown.')
    if baseline.get('allocation_authority') != 'capsule_global_resource_quota':
        reasons.append('Effective allocation authority is not a single Capsule GlobalResourceQuota.')
    if baseline.get('ambiguous_dimensions'):
        reasons.append('Observed allocation authority contains ambiguous dimensions.')
    if baseline.get('unsupported_dimensions'):
        reasons.append('Observed allocation contains unsupported dimensions.')
    if len(sources) != 1:
        reasons.append('Exactly one authoritative GlobalResourceQuota source is required.')
    if str(global_quota.get('served_version') or '') != _REQUIRED_API_VERSION:
        reasons.append('GlobalResourceQuota governance requires served capsule.clastix.io/v1beta2.')
    if _capsule_capability_state(tenant, _SHARED_CAPABILITY) != 'available':
        reasons.append('Capsule shared_global_quota capability is unavailable or degraded.')

    active_intents = _active_shared_intents(tenant.id)
    existing = _managed_shared_intent(tenant)
    if existing is not None and existing.status in {
        TenantAdvancedCapabilityStatus.READY.value,
        TenantAdvancedCapabilityStatus.DRIFTED.value,
    }:
        reasons.append('Shared allocation governance is already owned by a canonical KAORI intent.')
    elif active_intents:
        reasons.append(
            'An existing Capsule GlobalResourceQuota advanced intent already owns this Tenant resource path. '
            'Resolve that authority before allocation governance cutover.'
        )

    source = sources[0] if len(sources) == 1 else {}
    return {
        'supported': not reasons,
        'state': 'adopted_observed' if not reasons else 'control_unavailable',
        'reason': 'Eligible for explicit Capsule shared allocation governance cutover.'
        if not reasons
        else ' '.join(reasons),
        'authority': str(baseline.get('allocation_authority') or 'unknown'),
        'current_quota': dict(global_quota.get('quota') or {}),
        'source': source,
        'provider_api_version': str(global_quota.get('served_version') or ''),
        'shared_scope': str(baseline.get('shared_scope') or 'Tenant'),
    }


def _live_global_resource_quota(
    tenant: Tenant,
    *,
    expected_source: Mapping[str, Any] | None = None,
    require_resource_version_match: bool = True,
) -> tuple[dict[str, Any], dict[str, str]]:
    state = build_capsule_shared_allocation_cutover_state(tenant)
    managed_intent = _managed_shared_intent(tenant)
    if managed_intent is None and not state['supported']:
        raise ValueError(str(state['reason']))

    evidence = _tenant_evidence(tenant)
    capsule = evidence.get('capsule')
    capsule = capsule if isinstance(capsule, Mapping) else {}
    if tenant.provider_state != 'capsule' or _capsule_capability_state(tenant, _SHARED_CAPABILITY) != 'available':
        raise ValueError('Capsule shared allocation capability is unavailable or degraded.')

    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')
    api = runtime_adapter.build_client(cluster).custom_objects_api()

    source = dict(expected_source or state.get('source') or {})
    name = str(source.get('name') or (managed_intent.resource_name if managed_intent is not None else '')).strip()
    version = str(
        (managed_intent.provider_api_version if managed_intent is not None else state.get('provider_api_version'))
        or _REQUIRED_API_VERSION
    )
    if not name or version != _REQUIRED_API_VERSION:
        raise ValueError('Committed GlobalResourceQuota source identity is incomplete or unsupported.')

    try:
        current = api.get_cluster_custom_object(
            _CAPSULE_GROUP,
            version,
            _GLOBAL_QUOTA_PLURAL,
            name,
            _request_timeout=5,
        )
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError('Authoritative GlobalResourceQuota is no longer present.') from exc
        raise
    if not isinstance(current, dict):
        raise ValueError('Capsule GlobalResourceQuota provider response is invalid.')

    current_source = _source_reference(current)
    expected_uid = str(source.get('uid') or '')
    expected_rv = str(source.get('resource_version') or '')
    if expected_uid and current_source['uid'] and expected_uid != current_source['uid']:
        raise ValueError('GlobalResourceQuota UID changed; refresh provider evidence before governance mutation.')
    if (
        require_resource_version_match
        and expected_rv
        and current_source['resource_version']
        and expected_rv != current_source['resource_version']
    ):
        raise ValueError(
            'GlobalResourceQuota resourceVersion changed; refresh provider evidence before governance mutation.'
        )

    return current, current_source


def _profile_quota(profile: TenantResourceProfile) -> dict[str, str]:
    quota, _limits, _customized = _namespace_allocation_values(profile)
    return quota


def _new_shared_intent(
    tenant: Tenant,
    *,
    source: Mapping[str, str],
    profile: TenantResourceProfile,
    desired_spec: Mapping[str, Any],
    capacity_decision_id: int,
) -> TenantAdvancedCapabilityIntent:
    conflicts = _active_shared_intents(tenant.id)
    if conflicts:
        raise ValueError(
            'A GlobalResourceQuota intent already exists for this Tenant. Resolve the existing authority before cutover.'
        )

    intent = TenantAdvancedCapabilityIntent()
    intent.public_id = str(uuid.uuid4())
    intent.tenant = tenant
    intent.tenant_id = tenant.id
    intent.namespace = None
    intent.tenant_namespace_id = None
    intent.provider_key = 'capsule'
    intent.capability_key = _SHARED_CAPABILITY
    intent.resource_kind = 'global_resource_quota'
    intent.resource_name = str(source.get('name') or '')
    intent.provider_api_version = _REQUIRED_API_VERSION
    intent.desired_spec_json = deepcopy(dict(desired_spec))
    intent.status = TenantAdvancedCapabilityStatus.PENDING.value
    intent.generation = 1
    intent.reconciliation_evidence_json = {
        'allocation_governance_scope': _SHARED_SCOPE,
        'allocation_authority': 'capsule_global_resource_quota',
        'provenance': 'adopted_observed',
        'resource_profile_id': profile.public_id,
        'resource_profile_version': profile.version,
        'capacity_decision_id': capacity_decision_id,
        'expected_provider_source': dict(source),
        'secret_material_persisted': False,
    }
    db.session.add(intent)
    db.session.flush()
    return intent


def _commit_tenant_governance_evidence(
    tenant: Tenant,
    *,
    intent: TenantAdvancedCapabilityIntent,
    source: Mapping[str, str],
    profile: TenantResourceProfile,
    capacity_decision_id: int,
    provenance: str,
) -> None:
    evidence = _tenant_evidence(tenant)
    desired_spec = intent.desired_spec_json or {}
    effective_spec = intent.effective_spec_json or {}
    evidence['allocation_governance'] = {
        'scope': _SHARED_SCOPE,
        'authority': 'capsule_global_resource_quota',
        'control_state': 'kaori_managed',
        'intent_public_id': intent.public_id,
        'resource_name': intent.resource_name,
        'resource_profile_id': profile.public_id,
        'resource_profile_version': profile.version,
        'capacity_decision_id': capacity_decision_id,
        'desired_quota': dict((desired_spec.get('quota') or {}).get('hard') or {}),
        'effective_quota': dict((effective_spec.get('quota') or {}).get('hard') or {}),
        'desired_hash': intent.desired_hash,
        'effective_hash': intent.effective_hash,
        'provider_source': dict(source),
        'provenance': provenance,
        'updated_at': datetime.now(UTC).isoformat(),
        'secret_material_persisted': False,
    }
    tenant.provider_evidence_json = evidence


def cutover_capsule_global_quota_allocation(
    *,
    tenant_id: str,
    profile_id: int,
) -> TenantAdvancedCapabilityIntent:
    tenant = db.session.get(Tenant, tenant_id)
    profile = db.session.get(TenantResourceProfile, profile_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')
    if profile is None or not profile.enabled:
        raise ValueError('Selected Resource Profile is unavailable.')

    state = build_capsule_shared_allocation_cutover_state(tenant)
    if not state['supported']:
        raise ValueError(str(state['reason']))

    current, current_source = _live_global_resource_quota(
        tenant,
        expected_source=state['source'],
    )
    current_quota = _quota_from_global_resource(current)
    proposed_quota = _profile_quota(profile)
    capacity = enforce_shared_tenant_allocation_preflight(
        tenant=tenant,
        profile=profile,
        current_quota_hard=current_quota,
        proposed_quota_hard=proposed_quota,
    )
    desired_spec = _desired_shared_spec(current, proposed_quota)
    intent = _new_shared_intent(
        tenant,
        source=current_source,
        profile=profile,
        desired_spec=desired_spec,
        capacity_decision_id=capacity.id,
    )

    provider = _provider_from_committed_evidence(tenant)
    try:
        reconcile_capsule_advanced_intent(intent, provider=provider)
        if intent.status != TenantAdvancedCapabilityStatus.READY.value:
            raise ValueError(
                'Capsule provider read-back does not match the proposed shared allocation; '
                'KAORI will not mark allocation governance managed.'
            )
        cluster = db.session.get(Cluster, tenant.cluster_id)
        if cluster is None:
            raise ValueError('Tenant cluster no longer exists after provider reconciliation.')
        verified = runtime_adapter.build_client(cluster).custom_objects_api().get_cluster_custom_object(
            _CAPSULE_GROUP,
            _REQUIRED_API_VERSION,
            _GLOBAL_QUOTA_PLURAL,
            intent.resource_name,
            _request_timeout=5,
        )
        verified_source = _source_reference(verified if isinstance(verified, Mapping) else {})
        intent.reconciliation_evidence_json = {
            **(intent.reconciliation_evidence_json or {}),
            'allocation_governance_scope': _SHARED_SCOPE,
            'provenance': 'kaori_managed',
            'previous_provenance': 'adopted_observed',
            'provider_source': verified_source,
            'expected_provider_source': verified_source,
            'provider_mutation_performed': True,
        }
        _commit_tenant_governance_evidence(
            tenant,
            intent=intent,
            source=verified_source,
            profile=profile,
            capacity_decision_id=capacity.id,
            provenance='kaori_managed',
        )
        return intent
    except (ApiException, ValueError) as exc:
        intent.status = TenantAdvancedCapabilityStatus.FAILED.value
        intent.reconciliation_message = str(exc)[:1000]
        intent.reconciliation_evidence_json = {
            **(intent.reconciliation_evidence_json or {}),
            'allocation_governance_scope': _SHARED_SCOPE,
            'cutover_failure': {
                'at': datetime.now(UTC).isoformat(),
                'error': str(exc)[:1000],
                'provider_mutation_may_have_started': True,
            },
            'secret_material_persisted': False,
        }
        raise


def cutover_capsule_global_quota_allocation_committed(
    *,
    tenant_id: str,
    profile_id: int,
) -> TenantAdvancedCapabilityIntent:
    try:
        intent = cutover_capsule_global_quota_allocation(
            tenant_id=tenant_id,
            profile_id=profile_id,
        )
        db.session.commit()
        return intent
    except IntegrityError as exc:
        db.session.rollback()
        raise CapsuleSharedAllocationStateConflictError(
            'Committed Capsule shared allocation state changed during governance cutover. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _quota_differences(
    desired: Mapping[str, object],
    observed: Mapping[str, object],
) -> list[dict[str, str]]:
    differences: list[dict[str, str]] = []
    for key in sorted(set(desired) | set(observed)):
        left = str(desired.get(key) or 'Unbounded')
        right = str(observed.get(key) or 'Unbounded')
        if not _quantity_equal(key, left, right):
            differences.append(
                {
                    'dimension': key,
                    'kaori_value': left,
                    'provider_value': right,
                }
            )
    return differences


def _profile_matches_quota(
    profile: TenantResourceProfile,
    quota: Mapping[str, object],
) -> bool:
    return not _quota_differences(_profile_quota(profile), quota)


def observe_managed_capsule_shared_allocation(
    intent: TenantAdvancedCapabilityIntent,
) -> dict[str, Any]:
    tenant = intent.tenant
    if (intent.reconciliation_evidence_json or {}).get('allocation_governance_scope') != _SHARED_SCOPE:
        raise ValueError('Advanced Capsule intent is not the canonical Tenant shared allocation authority.')
    source = (intent.reconciliation_evidence_json or {}).get('provider_source')
    source = source if isinstance(source, Mapping) else {}
    current, current_source = _live_global_resource_quota(
        tenant,
        expected_source=source,
        require_resource_version_match=False,
    )
    observed_quota = _quota_from_global_resource(current)
    desired_spec = intent.desired_spec_json or {}
    desired_quota = dict((desired_spec.get('quota') or {}).get('hard') or {})
    differences = _quota_differences(desired_quota, observed_quota)
    return {
        'observed_at': datetime.now(UTC).isoformat(),
        'desired_quota': desired_quota,
        'observed_quota': observed_quota,
        'differences': differences,
        'provider_source': current_source,
        'observed_hash': _canonical_hash(current.get('spec') or {}),
        'provider_mutation_performed': False,
    }


def apply_managed_capsule_shared_allocation_drift_observation() -> dict[str, Any]:
    intents = (
        TenantAdvancedCapabilityIntent.query.filter(
            TenantAdvancedCapabilityIntent.resource_kind == 'global_resource_quota',
            TenantAdvancedCapabilityIntent.status.in_(
                (
                    TenantAdvancedCapabilityStatus.READY.value,
                    TenantAdvancedCapabilityStatus.DRIFTED.value,
                )
            ),
        )
        .order_by(TenantAdvancedCapabilityIntent.id.asc())
        .all()
    )
    drifted_intent_ids: list[int] = []
    observation_errors: list[dict[str, Any]] = []
    restored_intent_ids: list[int] = []
    for intent in intents:
        evidence = dict(intent.reconciliation_evidence_json or {})
        if evidence.get('allocation_governance_scope') != _SHARED_SCOPE:
            continue
        try:
            observation = observe_managed_capsule_shared_allocation(intent)
        except (ApiException, ValueError) as exc:
            intent.status = TenantAdvancedCapabilityStatus.DRIFTED.value
            evidence['allocation_drift'] = {
                'observed_at': datetime.now(UTC).isoformat(),
                'blocked_reasons': [str(exc)[:1000]],
                'provider_mutation_performed': False,
            }
            intent.reconciliation_evidence_json = evidence
            intent.reconciliation_message = 'Capsule shared allocation requires operator review.'
            drifted_intent_ids.append(intent.id)
            observation_errors.append(
                {
                    'intent_id': intent.id,
                    'tenant_id': intent.tenant_id,
                    'resource_name': intent.resource_name,
                    'reason': str(exc)[:1000],
                }
            )
            continue

        if observation['differences']:
            intent.status = TenantAdvancedCapabilityStatus.DRIFTED.value
            evidence['allocation_drift'] = {
                **observation,
                'blocked_reasons': [],
            }
            intent.reconciliation_evidence_json = evidence
            intent.reconciliation_message = 'Capsule shared allocation differs from committed KAORI intent.'
            drifted_intent_ids.append(intent.id)
        else:
            if intent.status == TenantAdvancedCapabilityStatus.DRIFTED.value or evidence.get('allocation_drift'):
                restored_intent_ids.append(intent.id)
            intent.status = TenantAdvancedCapabilityStatus.READY.value
            evidence.pop('allocation_drift', None)
            evidence['provider_source'] = observation['provider_source']
            evidence['expected_provider_source'] = observation['provider_source']
            intent.reconciliation_evidence_json = evidence
            intent.effective_spec_json = deepcopy(intent.desired_spec_json)
            intent.effective_hash = intent.desired_hash
            intent.reconciliation_message = 'Capsule shared allocation matches committed KAORI intent.'
    return {
        'drifted_intent_ids': sorted(set(drifted_intent_ids)),
        'restored_intent_ids': sorted(set(restored_intent_ids)),
        'observation_errors': observation_errors,
    }


def build_capsule_shared_drift_action_state(intent: TenantAdvancedCapabilityIntent) -> dict[str, Any]:
    evidence = intent.reconciliation_evidence_json or {}
    drift = evidence.get('allocation_drift')
    drift = dict(drift) if isinstance(drift, Mapping) else {}
    reasons = list(drift.get('blocked_reasons') or [])
    if evidence.get('allocation_governance_scope') != _SHARED_SCOPE:
        reasons.append('Intent is not the canonical Tenant shared allocation authority.')
    if intent.status != TenantAdvancedCapabilityStatus.DRIFTED.value:
        reasons.append('Shared allocation reconciliation requires committed Drifted state.')
    if intent.tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        reasons.append('Tenant is not Ready; reconciliation is frozen during teardown.')
    if intent.tenant.provider_state != 'capsule':
        reasons.append('Capsule provider is degraded or unavailable.')
    if _capsule_capability_state(intent.tenant, _SHARED_CAPABILITY) != 'available':
        reasons.append('Capsule shared_global_quota capability is unavailable or degraded.')
    return {
        'reapply_supported': not reasons,
        'accept_supported': not reasons,
        'blocked_reason': ' '.join(dict.fromkeys(reasons)),
        'drift': drift,
        'authority': 'capsule_global_resource_quota',
    }


def _fresh_drift_observation(intent: TenantAdvancedCapabilityIntent) -> tuple[dict[str, Any], dict[str, Any]]:
    state = build_capsule_shared_drift_action_state(intent)
    if not state['reapply_supported']:
        raise ValueError(str(state['blocked_reason']))
    drift = state['drift']
    expected_hash = str(drift.get('observed_hash') or '')
    source = drift.get('provider_source')
    source = source if isinstance(source, Mapping) else {}
    current, current_source = _live_global_resource_quota(intent.tenant, expected_source=source)
    current_spec = current.get('spec') if isinstance(current, Mapping) else {}
    current_hash = _canonical_hash(current_spec or {})
    if expected_hash and current_hash != expected_hash:
        raise ValueError('Capsule provider state changed since drift observation; run Tenant Sync and review again.')
    return current, current_source


def reapply_capsule_shared_allocation_intent(
    intent: TenantAdvancedCapabilityIntent,
) -> TenantAdvancedCapabilityIntent:
    current, current_source = _fresh_drift_observation(intent)
    desired_spec = intent.desired_spec_json or {}
    desired_quota = dict((desired_spec.get('quota') or {}).get('hard') or {})
    current_quota = _quota_from_global_resource(current)
    profile_id = (intent.reconciliation_evidence_json or {}).get('resource_profile_id')
    profile = TenantResourceProfile.query.filter_by(public_id=profile_id).first()
    if profile is None or not profile.enabled:
        raise ValueError('Committed Resource Profile lineage is unavailable for shared allocation reconciliation.')

    capacity = enforce_shared_tenant_allocation_preflight(
        tenant=intent.tenant,
        profile=profile,
        current_quota_hard=current_quota,
        proposed_quota_hard=desired_quota,
    )
    intent.reconciliation_evidence_json = {
        **(intent.reconciliation_evidence_json or {}),
        'expected_provider_source': current_source,
        'capacity_decision_id': capacity.id,
    }
    provider = _provider_from_committed_evidence(intent.tenant)
    reconcile_capsule_advanced_intent(intent, provider=provider)
    if intent.status != TenantAdvancedCapabilityStatus.READY.value:
        raise ValueError('Capsule shared allocation read-back does not match committed KAORI intent.')

    cluster = db.session.get(Cluster, intent.tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')
    verified = runtime_adapter.build_client(cluster).custom_objects_api().get_cluster_custom_object(
        _CAPSULE_GROUP,
        _REQUIRED_API_VERSION,
        _GLOBAL_QUOTA_PLURAL,
        intent.resource_name,
        _request_timeout=5,
    )
    verified_source = _source_reference(verified if isinstance(verified, Mapping) else {})
    evidence = dict(intent.reconciliation_evidence_json or {})
    evidence.pop('allocation_drift', None)
    evidence['provider_source'] = verified_source
    evidence['expected_provider_source'] = verified_source
    evidence['provenance'] = 'kaori_managed'
    intent.reconciliation_evidence_json = evidence
    intent.reconciliation_message = 'KAORI shared allocation intent was re-applied and provider-verified.'
    _commit_tenant_governance_evidence(
        intent.tenant,
        intent=intent,
        source=verified_source,
        profile=profile,
        capacity_decision_id=capacity.id,
        provenance='kaori_managed',
    )
    return intent


def accept_capsule_shared_provider_state(
    intent: TenantAdvancedCapabilityIntent,
) -> TenantAdvancedCapabilityIntent:
    current, current_source = _fresh_drift_observation(intent)
    current_spec = deepcopy(dict(current.get('spec') or {}))
    live_quota = _quota_from_global_resource(current)
    desired_spec = intent.desired_spec_json or {}
    committed_quota = dict((desired_spec.get('quota') or {}).get('hard') or {})
    profile_id = (intent.reconciliation_evidence_json or {}).get('resource_profile_id')
    profile = TenantResourceProfile.query.filter_by(public_id=profile_id).first()
    if profile is None:
        raise ValueError('Committed Resource Profile lineage is unavailable for provider-state acceptance.')

    capacity = enforce_shared_tenant_allocation_preflight(
        tenant=intent.tenant,
        profile=profile,
        current_quota_hard=committed_quota,
        proposed_quota_hard=live_quota,
    )
    intent.generation += 1
    intent.desired_spec_json = current_spec
    intent.effective_spec_json = deepcopy(current_spec)
    intent.desired_hash = _canonical_hash(current_spec)
    intent.effective_hash = intent.desired_hash
    intent.status = TenantAdvancedCapabilityStatus.READY.value
    intent.last_reconciled_at = datetime.now(UTC)
    evidence = dict(intent.reconciliation_evidence_json or {})
    history = list(evidence.get('allocation_history') or [])
    history.append(
        {
            'event': 'accept_provider_state',
            'at': datetime.now(UTC).isoformat(),
            'desired_before': committed_quota,
            'provider_accepted': live_quota,
        }
    )
    evidence.pop('allocation_drift', None)
    evidence.update(
        {
            'allocation_history': history,
            'provider_source': current_source,
            'expected_provider_source': current_source,
            'capacity_decision_id': capacity.id,
            'provenance': 'accepted_provider_state',
            'allocation_customized': not _profile_matches_quota(profile, live_quota),
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }
    )
    intent.reconciliation_evidence_json = evidence
    intent.reconciliation_message = 'Live Capsule shared allocation was accepted as the new KAORI intent.'
    _commit_tenant_governance_evidence(
        intent.tenant,
        intent=intent,
        source=current_source,
        profile=profile,
        capacity_decision_id=capacity.id,
        provenance='accepted_provider_state',
    )
    return intent


def reapply_capsule_shared_allocation_intent_committed(
    *,
    intent_id: int,
) -> TenantAdvancedCapabilityIntent:
    intent = db.session.get(TenantAdvancedCapabilityIntent, intent_id)
    if intent is None:
        raise ValueError('Selected Capsule shared allocation intent no longer exists.')
    try:
        result = reapply_capsule_shared_allocation_intent(intent)
        db.session.commit()
        return result
    except IntegrityError as exc:
        db.session.rollback()
        raise CapsuleSharedAllocationStateConflictError(
            'Committed Capsule shared allocation drift changed during Reapply KAORI Intent. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def accept_capsule_shared_provider_state_committed(
    *,
    intent_id: int,
) -> TenantAdvancedCapabilityIntent:
    intent = db.session.get(TenantAdvancedCapabilityIntent, intent_id)
    if intent is None:
        raise ValueError('Selected Capsule shared allocation intent no longer exists.')
    try:
        result = accept_capsule_shared_provider_state(intent)
        db.session.commit()
        return result
    except IntegrityError as exc:
        db.session.rollback()
        raise CapsuleSharedAllocationStateConflictError(
            'Committed Capsule shared allocation drift changed during Accept Provider State. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def get_capsule_shared_allocation_context(
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
        tenant.id: build_capsule_shared_allocation_cutover_state(tenant)
        for tenant in tenants
    }
    shared_intents = (
        TenantAdvancedCapabilityIntent.query.filter(
            TenantAdvancedCapabilityIntent.resource_kind == 'global_resource_quota',
            TenantAdvancedCapabilityIntent.status != TenantAdvancedCapabilityStatus.DISABLED.value,
        )
        .order_by(TenantAdvancedCapabilityIntent.updated_at.desc())
        .all()
    )
    governed = [
        intent
        for intent in shared_intents
        if (intent.reconciliation_evidence_json or {}).get('allocation_governance_scope') == _SHARED_SCOPE
    ]
    drifted = [
        intent for intent in governed if intent.status == TenantAdvancedCapabilityStatus.DRIFTED.value
    ]
    visible_drifted, drift_pagination = paginate_sequence(
        drifted,
        page=drift_page,
        per_page=drift_per_page,
    )
    return {
        'capsule_shared_tenants': tenants,
        'capsule_shared_cutover_state': cutover_state,
        'capsule_shared_cutover_supported': any(item['supported'] for item in cutover_state.values()),
        'capsule_shared_intents': governed,
        'capsule_shared_drift_intents': visible_drifted,
        'capsule_shared_drift_pagination': drift_pagination,
        'capsule_shared_drift_state': {
            str(intent.id): build_capsule_shared_drift_action_state(intent)
            for intent in visible_drifted
        },
    }
