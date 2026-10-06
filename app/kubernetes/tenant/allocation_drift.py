from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import InvalidOperation
from typing import Any

from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_cutover import (
    allocation_control_state,
    reconcile_adopted_native_allocation,
)
from app.kubernetes.tenant.allocation_observation import observe_native_namespace_allocation
from app.kubernetes.tenant.capacity_governance import enforce_observed_namespace_allocation_preflight
from app.kubernetes.tenant.validation import COUNT_QUOTA_KEYS, validate_profile_spec, validate_storage_policy
from app.models import Cluster
from app.models.tenant import (
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantResourceProfile,
)

_MANAGED_BY_VALUE = 'kaori'


def _quantity_equal(key: str, left: str, right: str) -> bool:
    if key in COUNT_QUOTA_KEYS:
        try:
            return int(left) == int(right)
        except (TypeError, ValueError):
            return False
    try:
        return parse_quantity(left) == parse_quantity(right)
    except (InvalidOperation, TypeError, ValueError):
        return left == right


def _quota_value_changed(key: str, desired: str, observed: str) -> bool:
    if desired == observed:
        return False
    if not desired or not observed:
        return True
    return not _quantity_equal(key, desired, observed)


def _quantity_value_changed(desired: str, observed: str) -> bool:
    if desired == observed:
        return False
    if not desired or not observed:
        return True
    try:
        return parse_quantity(desired) != parse_quantity(observed)
    except (InvalidOperation, TypeError, ValueError):
        return desired != observed


def _dimension_rows(
    desired_quota: Mapping[str, str],
    desired_limits: Mapping[str, Mapping[str, str]],
    desired_storage: Mapping[str, str],
    observed_quota: Mapping[str, str],
    observed_limits: Mapping[str, Mapping[str, str]],
    observed_storage: Mapping[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key in sorted(set(desired_quota) | set(observed_quota)):
        desired = str(desired_quota.get(key) or '')
        observed = str(observed_quota.get(key) or '')
        if not _quota_value_changed(key, desired, observed):
            continue
        rows.append(
            {
                'dimension': key,
                'kaori_value': desired or 'Unbounded',
                'provider_value': observed or 'Unbounded',
            }
        )

    fields = sorted(set(desired_limits) | set(observed_limits))
    for field in fields:
        desired_values = desired_limits.get(field) or {}
        observed_values = observed_limits.get(field) or {}
        for key in sorted(set(desired_values) | set(observed_values)):
            desired = str(desired_values.get(key) or '')
            observed = str(observed_values.get(key) or '')
            if not _quantity_value_changed(desired, observed):
                continue
            rows.append(
                {
                    'dimension': f'{field}.{key}',
                    'kaori_value': desired or 'Unbounded',
                    'provider_value': observed or 'Unbounded',
                }
            )
    for field in sorted(set(desired_storage) | set(observed_storage)):
        desired = str(desired_storage.get(field) or '')
        observed = str(observed_storage.get(field) or '')
        if not _quantity_value_changed(desired, observed):
            continue
        rows.append(
            {
                'dimension': f'pvc.{field}.storage',
                'kaori_value': desired or 'Unbounded',
                'provider_value': observed or 'Unbounded',
            }
        )
    return rows


def allocation_differences(
    record: TenantNamespace,
    observation: Mapping[str, Any],
) -> list[dict[str, str]]:
    return _dimension_rows(
        dict(record.allocation_quota_json or {}),
        dict(record.allocation_limit_defaults_json or {}),
        dict(record.allocation_storage_policy_json or {}),
        dict(observation.get('quota') or {}),
        dict(observation.get('limits') or {}),
        dict(observation.get('storage_policy') or {}),
    )


def _ownership_findings(record: TenantNamespace, observation: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    tenant_id = str(record.environment.tenant.id)
    resources = observation.get('source_resources')
    for item in resources if isinstance(resources, list) else []:
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get('kind') or 'Resource')
        name = str(item.get('name') or 'unknown')
        manager = str(item.get('managed_by') or '')
        observed_tenant_id = str(item.get('tenant_id') or '')
        if manager != _MANAGED_BY_VALUE:
            findings.append(f'{kind}/{name} no longer carries KAORI allocation ownership metadata.')
        if observed_tenant_id != tenant_id:
            findings.append(f'{kind}/{name} no longer maps to the committed KAORI Tenant identity.')
    return findings


def _allocation_drift_payload(
    record: TenantNamespace,
    observation: Mapping[str, Any],
    *,
    observed_at: datetime,
) -> dict[str, Any]:
    differences = allocation_differences(record, observation)
    ownership_findings = _ownership_findings(record, observation)
    control_state = str(observation.get('control_state') or 'control_unavailable')
    blocked_reasons = list(ownership_findings)
    if control_state != 'observed':
        blocked_reasons.append(
            str(observation.get('control_reason') or 'Provider allocation authority is ambiguous or unsupported.')
        )
    return {
        'source': 'live_provider_observation',
        'provider': record.environment.tenant.provider_key,
        'authority': record.environment.tenant.reconciliation_authority,
        'observed_at': observed_at.isoformat(),
        'desired': {
            'quota': dict(record.allocation_quota_json or {}),
            'limits': dict(record.allocation_limit_defaults_json or {}),
            'storage_policy': dict(record.allocation_storage_policy_json or {}),
            'effective_hash': record.effective_hash,
            'resource_profile_id': (record.resource_profile.public_id if record.resource_profile is not None else None),
            'resource_profile_version': record.resource_profile_version,
        },
        'observed': dict(observation),
        'differences': differences,
        'ownership_findings': ownership_findings,
        'blocked_reasons': blocked_reasons,
        'observed_matches_desired': not differences and not blocked_reasons,
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }


def apply_managed_allocation_drift_observation() -> dict[str, Any]:
    """Observe KAORI-managed allocation contracts without mutating providers."""

    records = (
        TenantNamespace.query.filter(
            TenantNamespace.provisioning_status.in_(
                (
                    TenantNamespaceProvisioningStatus.READY.value,
                    TenantNamespaceProvisioningStatus.DRIFTED.value,
                )
            )
        )
        .order_by(TenantNamespace.cluster_id.asc(), TenantNamespace.id.asc())
        .all()
    )
    now = datetime.now(UTC)
    clients: dict[str, Any] = {}
    drifted_ids: list[int] = []
    drifted: list[dict[str, str]] = []
    observed_ids: list[int] = []
    errors: list[dict[str, str]] = []

    for record in records:
        control_state = allocation_control_state(record)
        if control_state != 'kaori_managed':
            continue

        evidence = dict(record.provisioning_evidence_json or {})
        provider_absence = evidence.get('provider_observation')
        if (
            record.provisioning_status == TenantNamespaceProvisioningStatus.DRIFTED.value
            and isinstance(provider_absence, Mapping)
            and provider_absence.get('observed_absent') is True
        ):
            continue

        tenant = record.environment.tenant
        if tenant.provider_key != 'native_kubernetes' or tenant.reconciliation_authority != 'native_kubernetes':
            errors.append(
                {
                    'tenant_namespace_id': str(record.id),
                    'namespace': record.namespace,
                    'reason': (
                        'Managed allocation drift observation has no admitted provider adapter for '
                        f'{tenant.provider_key}/{tenant.reconciliation_authority}.'
                    ),
                }
            )
            continue

        try:
            cluster_id = str(record.cluster_id)
            client = clients.get(cluster_id)
            if client is None:
                cluster = db.session.get(Cluster, record.cluster_id)
                if cluster is None:
                    raise ValueError('Tenant namespace cluster no longer exists.')
                client = runtime_adapter.build_client(cluster)
                clients[cluster_id] = client
            observation = observe_native_namespace_allocation(
                client.core_api(),
                record.namespace,
            )
        except (ApiException, OSError, RuntimeError, ValueError) as exc:
            errors.append(
                {
                    'tenant_namespace_id': str(record.id),
                    'namespace': record.namespace,
                    'reason': str(exc)[:500],
                }
            )
            continue

        observed_ids.append(record.id)
        payload = _allocation_drift_payload(record, observation, observed_at=now)
        should_drift = (
            bool(payload['differences'])
            or bool(payload['blocked_reasons'])
            or record.provisioning_status == TenantNamespaceProvisioningStatus.DRIFTED.value
            and isinstance(evidence.get('allocation_drift'), Mapping)
        )
        if not should_drift:
            continue

        evidence['allocation_drift'] = payload
        record.provisioning_evidence_json = evidence
        record.provisioning_status = TenantNamespaceProvisioningStatus.DRIFTED.value
        if payload['observed_matches_desired']:
            record.provisioning_message = (
                'Live provider allocation now matches committed KAORI intent, but prior drift remains '
                'pending explicit reconciliation confirmation.'
            )
        elif payload['blocked_reasons']:
            record.provisioning_message = (
                'Allocation drift detected, but provider authority/ownership requires review before reconciliation.'
            )
        else:
            record.provisioning_message = (
                'Live provider allocation differs from committed KAORI intent. '
                'Choose Reapply KAORI Intent or Accept Provider State.'
            )
        drifted_ids.append(record.id)
        drifted.append(
            {
                'tenant_namespace_id': str(record.id),
                'cluster_id': str(record.cluster_id),
                'namespace': record.namespace,
                'reason': record.provisioning_message or 'Allocation drift requires review.',
            }
        )

    if drifted_ids:
        db.session.flush()
    return {
        'observed_namespace_ids': observed_ids,
        'drifted_namespace_ids': drifted_ids,
        'drifted_namespaces': drifted,
        'observation_errors': errors,
    }


def apply_provider_mirrored_policy_observation() -> dict[str, Any]:
    """Refresh provider-owned Capsule Namespace policy mirrors without creating drift."""

    records = (
        TenantNamespace.query.filter(
            TenantNamespace.provisioning_status.in_(
                (
                    TenantNamespaceProvisioningStatus.READY.value,
                    TenantNamespaceProvisioningStatus.DRIFTED.value,
                )
            )
        )
        .order_by(TenantNamespace.cluster_id.asc(), TenantNamespace.id.asc())
        .all()
    )
    clients: dict[str, Any] = {}
    mirrored_ids: list[int] = []
    updated_ids: list[int] = []
    errors: list[dict[str, str]] = []
    now = datetime.now(UTC)

    for record in records:
        evidence = dict(record.provisioning_evidence_json or {})
        if str(evidence.get('allocation_control_state') or '') != 'provider_mirrored_policy':
            continue

        tenant = record.environment.tenant
        if tenant.provider_key != 'capsule' or tenant.reconciliation_authority != 'capsule':
            errors.append(
                {
                    'tenant_namespace_id': str(record.id),
                    'namespace': record.namespace,
                    'reason': 'Provider-mirrored Namespace policy requires Capsule authority.',
                }
            )
            continue

        try:
            cluster_id = str(record.cluster_id)
            client = clients.get(cluster_id)
            if client is None:
                cluster = db.session.get(Cluster, record.cluster_id)
                if cluster is None:
                    raise ValueError('Tenant namespace cluster no longer exists.')
                client = runtime_adapter.build_client(cluster)
                clients[cluster_id] = client

            observation = observe_native_namespace_allocation(
                client.core_api(),
                record.namespace,
            )
            if observation.get('unsupported_dimensions') or observation.get('ambiguous_dimensions'):
                raise ValueError('Capsule-generated Namespace policy contains unsupported or ambiguous dimensions.')

            limits = validate_profile_spec({}, dict(observation.get('limits') or {}))[1]
            storage_policy = validate_storage_policy(dict(observation.get('storage_policy') or {}))
        except (ApiException, OSError, RuntimeError, ValueError) as exc:
            errors.append(
                {
                    'tenant_namespace_id': str(record.id),
                    'namespace': record.namespace,
                    'reason': str(exc)[:500],
                }
            )
            continue

        mirrored_ids.append(record.id)
        changed = limits != dict(record.allocation_limit_defaults_json or {}) or storage_policy != dict(
            record.allocation_storage_policy_json or {}
        )

        record.allocation_quota_json = {}
        record.allocation_limit_defaults_json = limits
        record.allocation_storage_policy_json = storage_policy
        record.effective_hash = str(observation.get('effective_hash') or '') or record.effective_hash
        record.desired_hash = record.effective_hash
        record.last_reconciled_at = now
        record.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
        record.provisioning_message = (
            'Capsule-generated Container/PVC policy is mirrored from provider authority; '
            'provider-owned changes update committed KAORI state without false drift.'
        )

        profile = record.resource_profile
        if profile is not None:
            profile_changed = limits != dict(profile.limit_defaults_json or {}) or storage_policy != dict(
                getattr(profile, 'storage_policy_json', {}) or {}
            )
            if profile_changed:
                profile.limit_defaults_json = limits
                profile.storage_policy_json = storage_policy
                profile.version = int(profile.version or 1) + 1
                record.resource_profile_version = profile.version

        evidence['allocation_control_state'] = 'provider_mirrored_policy'
        evidence['allocation'] = {
            **dict(observation),
            'provenance': 'provider_mirrored_policy',
            'quota_authority': 'capsule',
            'policy_authority': 'capsule_generated_namespace_policy',
            'resource_profile_id': profile.public_id if profile is not None else None,
            'resource_profile_version': record.resource_profile_version,
        }
        evidence['provider_policy_mirror'] = {
            **dict(evidence.get('provider_policy_mirror') or {}),
            'mirrored_at': now.isoformat(),
            'provider_mutation_performed': False,
            'provider_values_changed': changed,
        }
        evidence.pop('allocation_drift', None)
        record.provisioning_evidence_json = evidence
        if changed:
            updated_ids.append(record.id)

    if mirrored_ids:
        db.session.flush()
    return {
        'mirrored_namespace_ids': mirrored_ids,
        'updated_namespace_ids': updated_ids,
        'observation_errors': errors,
        'provider_mutation_performed': False,
    }


def _drift_evidence(record: TenantNamespace) -> dict[str, Any]:
    evidence = dict(record.provisioning_evidence_json or {})
    drift = evidence.get('allocation_drift')
    if not isinstance(drift, dict):
        raise ValueError('Selected Namespace has no committed allocation-drift evidence.')
    return drift


def build_allocation_drift_action_state(record: TenantNamespace) -> dict[str, Any]:
    try:
        drift = _drift_evidence(record)
    except ValueError as exc:
        return {
            'is_allocation_drift': False,
            'reapply_supported': False,
            'accept_supported': False,
            'blocked_reason': str(exc),
        }

    tenant = record.environment.tenant
    blocked = list(drift.get('blocked_reasons') or [])
    if record.provisioning_status != TenantNamespaceProvisioningStatus.DRIFTED.value:
        blocked.append('Allocation reconciliation requires a committed Drifted Namespace state.')
    if tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        blocked.append('Tenant is not Ready; allocation reconciliation is unavailable during teardown.')
    if allocation_control_state(record) != 'kaori_managed':
        blocked.append('Allocation control is not KAORI Managed.')
    if tenant.provider_key != 'native_kubernetes' or tenant.reconciliation_authority != 'native_kubernetes':
        blocked.append('No admitted reconciliation adapter exists for the current provider authority.')
    if record.resource_profile is None:
        blocked.append('Committed Resource Profile lineage is missing.')

    return {
        'is_allocation_drift': True,
        'reapply_supported': not blocked,
        'accept_supported': not blocked,
        'blocked_reason': ' '.join(str(item) for item in blocked),
        'drift': drift,
    }


def _live_observation_for_action(
    record: TenantNamespace,
    drift: Mapping[str, Any],
) -> dict[str, Any]:
    observed = drift.get('observed')
    if not isinstance(observed, Mapping):
        raise ValueError('Committed provider observation is missing from allocation-drift evidence.')
    expected_hash = str(observed.get('effective_hash') or '')
    if not expected_hash:
        raise ValueError('Committed provider observation hash is missing; run Tenant Sync again.')

    cluster = db.session.get(Cluster, record.cluster_id)
    if cluster is None:
        raise ValueError('Tenant namespace cluster no longer exists.')
    live = observe_native_namespace_allocation(
        runtime_adapter.build_client(cluster).core_api(),
        record.namespace,
    )
    if str(live.get('effective_hash') or '') != expected_hash:
        raise ValueError(
            'Live provider allocation changed again after the committed drift observation; run Tenant Sync again.'
        )
    if live.get('control_state') != 'observed':
        raise ValueError(
            str(live.get('control_reason') or 'Provider allocation authority is no longer safe to reconcile.')
        )
    findings = _ownership_findings(record, live)
    if findings:
        raise ValueError(' '.join(findings))
    return live


def reapply_kaori_allocation_intent(record: TenantNamespace) -> TenantNamespace:
    action = build_allocation_drift_action_state(record)
    if not action['reapply_supported']:
        raise ValueError(str(action['blocked_reason']))

    drift = dict(action['drift'])
    profile = record.resource_profile
    if profile is None:
        raise ValueError('Committed Resource Profile lineage is missing.')
    observed = drift.get('observed')
    if not isinstance(observed, Mapping):
        raise ValueError('Committed provider observation is missing.')

    # Re-read the provider before capacity admission so the decision is based on
    # the allocation that would actually be changed. A second hash check inside
    # reconcile_adopted_native_allocation protects the write from races that
    # happen after this preflight.
    live = _live_observation_for_action(record, drift)
    capacity_decision = enforce_observed_namespace_allocation_preflight(
        record=record,
        profile=profile,
        current_quota_hard=dict(live.get('quota') or {}),
        proposed_quota_hard=record.allocation_quota_json or {},
    )
    reconcile_adopted_native_allocation(
        record,
        profile=profile,
        resource_profile_version=record.resource_profile_version or profile.version,
        allocation_customized=record.allocation_customized,
        capacity_decision_id=capacity_decision.id,
        quota_hard=dict(record.allocation_quota_json or {}),
        limit_defaults=dict(record.allocation_limit_defaults_json or {}),
        storage_policy=dict(record.allocation_storage_policy_json or {}),
        operation='reapply_kaori_intent',
        expected_observed_hash=str(live.get('effective_hash') or ''),
        failure_status=TenantNamespaceProvisioningStatus.DRIFTED.value,
    )
    return record


def _profile_matches_observation(
    profile: TenantResourceProfile,
    observation: Mapping[str, Any],
) -> bool:
    profile_quota, profile_limits = validate_profile_spec(
        profile.quota_hard_json or {},
        profile.limit_defaults_json or {},
    )
    profile_storage = validate_storage_policy(getattr(profile, 'storage_policy_json', {}) or {})
    return not _dimension_rows(
        profile_quota,
        profile_limits,
        profile_storage,
        dict(observation.get('quota') or {}),
        dict(observation.get('limits') or {}),
        dict(observation.get('storage_policy') or {}),
    )


def _managed_resource_name(observation: Mapping[str, Any], kind: str) -> str:
    for item in observation.get('source_resources') or []:
        if isinstance(item, Mapping) and item.get('kind') == kind:
            return str(item.get('name') or '')
    return ''


def _managed_resource_names(observation: Mapping[str, Any]) -> dict[str, str]:
    return {
        'quota': _managed_resource_name(observation, 'ResourceQuota'),
        'limit_range': _managed_resource_name(observation, 'LimitRange'),
    }


def _provider_state_profile_sync_enabled(profile: TenantResourceProfile) -> bool:
    description = str(profile.description or '')
    return profile.profile_class == 'custom' and description.startswith(
        (
            'Explicit governance-cutover profile materialized',
            'Provider-equivalent namespaced',
            'Provider-equivalent Capsule',
        )
    )


def accept_provider_allocation_state(record: TenantNamespace) -> TenantNamespace:
    action = build_allocation_drift_action_state(record)
    if not action['accept_supported']:
        raise ValueError(str(action['blocked_reason']))

    drift = dict(action['drift'])
    profile = record.resource_profile
    if profile is None:
        raise ValueError('Committed Resource Profile lineage is missing.')
    live = _live_observation_for_action(record, drift)
    quota, limits = validate_profile_spec(
        dict(live.get('quota') or {}),
        dict(live.get('limits') or {}),
    )
    storage_policy = validate_storage_policy(dict(live.get('storage_policy') or {}))

    capacity_decision = enforce_observed_namespace_allocation_preflight(
        record=record,
        profile=profile,
        current_quota_hard=record.allocation_quota_json or {},
        proposed_quota_hard=quota,
    )

    now = datetime.now(UTC)
    evidence = dict(record.provisioning_evidence_json or {})
    previous_allocation = evidence.get('allocation')
    previous_provenance = (
        str(previous_allocation.get('provenance') or '') if isinstance(previous_allocation, Mapping) else ''
    ) or 'kaori_managed'
    history = list(evidence.get('allocation_history') or [])
    history.append(
        {
            'event': 'accept_provider_state',
            'at': now.isoformat(),
            'from': {
                'control_state': 'kaori_managed',
                'quota': dict(record.allocation_quota_json or {}),
                'limits': dict(record.allocation_limit_defaults_json or {}),
                'storage_policy': dict(record.allocation_storage_policy_json or {}),
                'effective_hash': record.effective_hash,
            },
            'to': {
                'control_state': 'kaori_managed',
                'quota': quota,
                'limits': limits,
                'storage_policy': storage_policy,
                'effective_hash': live['effective_hash'],
            },
        }
    )

    managed_names = _managed_resource_names(live)
    evidence.update(
        {
            'allocation_control_state': 'kaori_managed',
            'managed_resource_names': managed_names,
            'allocation': {
                **live,
                'provenance': 'accepted_provider_state',
                'previous_provenance': previous_provenance,
                'resource_profile_id': profile.public_id,
                'resource_profile_version': record.resource_profile_version or profile.version,
                'capacity_decision_id': capacity_decision.id,
            },
            'allocation_history': history,
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }
    )
    evidence.pop('allocation_drift', None)
    evidence.pop('allocation_reconcile_failure', None)

    if _provider_state_profile_sync_enabled(profile):
        profile.quota_hard_json = quota
        profile.limit_defaults_json = limits
        profile.storage_policy_json = storage_policy
        profile.version = int(profile.version or 1) + 1
        record.resource_profile_version = profile.version
        evidence['provider_state_profile_sync'] = {
            'profile_id': profile.public_id,
            'profile_version': profile.version,
            'at': now.isoformat(),
            'provider_values_accepted': True,
        }

    record.allocation_quota_json = quota
    record.allocation_limit_defaults_json = limits
    record.allocation_storage_policy_json = storage_policy
    record.allocation_customized = not _profile_matches_observation(profile, live)
    record.capacity_decision_id = capacity_decision.id
    record.provisioning_evidence_json = evidence
    record.desired_hash = str(live['effective_hash'])
    record.effective_hash = str(live['effective_hash'])
    record.last_reconciled_at = now
    record.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
    record.provisioning_message = (
        'Provider allocation was accepted as the new governed KAORI intent without a provider write.'
    )
    return record


def reapply_kaori_allocation_intent_committed(*, namespace_id: int) -> TenantNamespace:
    record = db.session.get(TenantNamespace, namespace_id)
    if record is None:
        raise ValueError('Selected Tenant namespace no longer exists.')
    try:
        reapply_kaori_allocation_intent(record)
        db.session.commit()
        return record
    except (ApiException, ValueError):
        db.session.commit()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise RuntimeError(
            'Committed allocation drift changed during Reapply KAORI Intent. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def accept_provider_allocation_state_committed(*, namespace_id: int) -> TenantNamespace:
    record = db.session.get(TenantNamespace, namespace_id)
    if record is None:
        raise ValueError('Selected Tenant namespace no longer exists.')
    try:
        accept_provider_allocation_state(record)
        db.session.commit()
        return record
    except ValueError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise RuntimeError(
            'Committed allocation drift changed during Accept Provider State. Refresh and retry.'
        ) from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise
