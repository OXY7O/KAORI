from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.common.pagination import paginate_sequence
from app.extensions.db import db
from app.kubernetes.tenant.capacity_governance import enforce_capsule_tenant_resource_quota_preflight
from app.kubernetes.tenant.capsule_tenant_quota_contract import (
    _AUTHORITY,
    _CAPABILITY,
    _CONTROL_DRIFTED,
    _CONTROL_MANAGED,
)
from app.kubernetes.tenant.capsule_tenant_quota_provider import (
    _live_allocation,
    _patch_resource_quotas,
    _prove_mutation_capability,
    _prove_read_capability,
    _read_live_tenant,
    _verify_effective,
)
from app.kubernetes.tenant.capsule_tenant_quota_support import (
    _GovernanceCommitContext,
    _allocation_baseline,
    _baseline_source,
    _baseline_tenant_quota,
    _canonical_hash,
    _capsule_capability_state,
    _commit_governance as _commit_governance_impl,
    _desired_resource_quotas,
    _governance,
    _lineage_profile,
    _managed_state,
    _namespace_count,
    _profile,
    _profile_matches_quota,
    _quota_contract_from_observation,
    _quota_differences,
    _quota_for_profile,
    _record_failure,
    _resource_quota_authority_context,
    _resource_quotas,
)
from app.kubernetes.tenant.providers import TenantProviderState
from app.kubernetes.tenant.service import _validate_resource_profile_attachment_controls
from app.kubernetes.tenant.validation import validate_profile_spec
from app.models.tenant import (
    Tenant,
    TenantLifecycleStatus,
    TenantResourceProfile,
)



class CapsuleTenantQuotaStateConflictError(RuntimeError):
    """Committed Capsule Tenant quota governance changed while applying an action."""


def _commit_governance(tenant: Tenant, **values: Any) -> None:
    _commit_governance_impl(tenant, _GovernanceCommitContext(**values))


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
            raise ValueError(
                'Capsule Tenant quota scope changed outside KAORI; run Tenant Sync before changing allocation.'
            )
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
            blocked_reasons.append(f'Capsule Tenant quota scope changed from {desired_scope} to {observed_scope}.')
        desired_resource_quotas = governance.get('desired_resource_quotas')
        desired_resource_quotas = dict(desired_resource_quotas) if isinstance(desired_resource_quotas, Mapping) else {}
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
    desired_resource_quotas = dict(desired_resource_quotas) if isinstance(desired_resource_quotas, Mapping) else {}
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
    cutover_state = {tenant.id: build_capsule_tenant_quota_cutover_state(tenant) for tenant in tenants}
    cutover_tenants = [
        tenant
        for tenant in tenants
        if cutover_state[tenant.id].get('authority') == _AUTHORITY and not _managed_state(tenant)
    ]
    blocked_cutover_tenants = [
        tenant for tenant in cutover_tenants if not bool(cutover_state[tenant.id].get('supported'))
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
        'capsule_tenant_quota_cutover_supported': any(item['supported'] for item in cutover_state.values()),
        'capsule_tenant_quota_managed': managed,
        'capsule_tenant_quota_drifted': visible_drifted,
        'capsule_tenant_quota_drift_pagination': pagination,
        'capsule_tenant_quota_drift_state': {
            tenant.id: build_capsule_tenant_quota_drift_action_state(tenant) for tenant in visible_drifted
        },
        'capsule_tenant_quota_governance': {
            tenant.id: _governance(tenant) for tenant in tenants if _governance(tenant).get('authority') == _AUTHORITY
        },
    }
