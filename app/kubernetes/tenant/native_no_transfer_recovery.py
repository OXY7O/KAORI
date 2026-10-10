"""Governed, evidence-only Native failure-before-write recovery (#1104).

The assessment reads provider objects but never patches Kubernetes. Only a
different, authorized reviewer may acknowledge exact immutable evidence.
The original requester must still create a NEW independently reviewed plan;
no old acceptance, preview, or Release authorization is inherited.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.native_handoff_dry_run import _read_resource
from app.kubernetes.tenant.native_handoff_executor import _approved_component_for_preview, _component_key
from app.kubernetes.tenant.native_handoff_recovery import summarize_native_handoff_recovery
from app.kubernetes.tenant.native_handoff_readback import _latest_native_dry_run
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan, _checked_recently, _plan_hash,
    latest_release_handoff_approval, latest_release_handoff_plan,
)
from app.kubernetes.tenant.release_preflight import review_tenant_release_preflight_committed
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_ASSESS_TARGET = 'kubernetes_tenant_release_native_no_transfer_assessment'
_DECISION_TARGET = 'kubernetes_tenant_release_native_no_transfer_decision'
_EXECUTOR_TARGET = 'kubernetes_tenant_release_native_handoff_execution'
_READBACK_TARGET = 'kubernetes_tenant_release_native_handoff_readback'


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()


def _latest(tenant_id: str, target: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=target, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(event.metadata_json or {}) if event else None


def latest_no_transfer_assessment(tenant_id: str) -> dict[str, Any] | None:
    return _latest(tenant_id, _ASSESS_TARGET)


def latest_no_transfer_decision(tenant_id: str) -> dict[str, Any] | None:
    return _latest(tenant_id, _DECISION_TARGET)


def _source_history(tenant_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Permit exactly one provably failed-before-write attempt; all else fails closed.

    A 0/2 summary by itself is NOT proof; the complete committed executor
    sequence and any external read-back for the SAME SHA are mandatory inputs.
    """
    events = (
        AuditEvent.query.filter(
            AuditEvent.target_id == tenant_id,
            AuditEvent.target_type.in_((_EXECUTOR_TARGET, _READBACK_TARGET)),
        ).order_by(AuditEvent.id.asc()).all()
    )
    attempts: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for event in events:
        record = dict(event.metadata_json or {})
        sha = record.get('plan_sha256')
        if not isinstance(sha, str) or len(sha) != 64:
            raise ValueError('Incomplete historical provider operation; independent recovery investigation required.')
        if sha != plan['plan_sha256']:
            continue
        item = {
            'event_id': event.id, 'actor_id': event.actor_user_id,
            'action': event.action, 'metadata': record,
        }
        if event.target_type == _EXECUTOR_TARGET:
            attempts.append(item)
        else:
            observations.append(item)
    if len(attempts) != 2 or observations:
        raise ValueError('Provider history is ambiguous or includes external read-back; recovery is blocked.')
    started, failure = attempts
    first, last = started['metadata'], failure['metadata']
    if (
        started['action'] != 'tenant.release.native_handoff_started'
        or failure['action'] != 'tenant.release.native_handoff_recovery_required'
        or started['actor_id'] != failure['actor_id']
        or type(started['actor_id']) is not int
        or first.get('status') != 'in_progress'
        or last.get('status') != 'partial_handoff_recovery_required'
        or not isinstance(last.get('errors'), list) or not last['errors']
        or type(last.get('verified_count')) is not int or last['verified_count'] != 0
        or type(last.get('expected_component_count')) is not int
        or last['expected_component_count'] != len([
            row for row in plan.get('handoff_components', [])
            if row.get('handoff') == 'external_acceptance_required'
        ])
        or last.get('provider_mutation_performed') is not False
        or last.get('provider_handoff_verified') is not False
        or last.get('release_authorized') is not False
        or last.get('verified_components') != []
        or first.get('release_authorized') is not False
        or last.get('tenant_id') != tenant_id
        or last.get('cluster_id') != plan.get('cluster_id')
        or last.get('generation') != plan.get('generation')
        or any(
            row.get('plan_sha256') != plan['plan_sha256']
            or row.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
            for row in (first, last)
        )
    ):
        raise ValueError('An executor attempt may have mutated resources or its evidence is incomplete.')
    # Both audit timestamps must be valid, ordered and in the past. A
    # missing/rewritten receipt is not evidence of a failed-before-write run.
    try:
        began_at = datetime.fromisoformat(str(first.get('started_at') or ''))
        failed_at = datetime.fromisoformat(str(last.get('checked_at') or ''))
    except ValueError as exc:
        raise ValueError('Executor audit chronology is incomplete.') from exc
    if (
        began_at.tzinfo is None or failed_at.tzinfo is None
        or began_at > failed_at or failed_at > datetime.now(UTC)
    ):
        raise ValueError('Executor audit chronology is not trustworthy.')
    return {
        'digest': _sha(attempts),
        'executor_actor_id': started['actor_id'],
        'failed_event_id': failure['event_id'],
    }


def _require_expired_plan(tenant_id: str, plan_sha256: str) -> dict[str, Any]:
    plan = latest_release_handoff_plan(tenant_id)
    approved = latest_release_handoff_approval(tenant_id)
    if (
        not plan or not approved or plan.get('plan_sha256') != plan_sha256
        or plan.get('tenant_id') != tenant_id or plan.get('provider') != 'native_kubernetes'
        or _plan_hash(plan) != plan_sha256 or len(plan_sha256) != 64
        or plan.get('status') != 'pending_independent_approval'
        or approved.get('plan_sha256') != plan_sha256
        or approved.get('status') != 'acknowledged_pending_provider_handoff'
        or approved.get('requested_by') != plan.get('requested_by')
        or type(approved.get('approved_by')) is not int
        or approved['approved_by'] == plan.get('requested_by')
        or approved.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or approved.get('provider_handoff_verified') is not False
        or approved.get('release_authorized') is not False
    ):
        raise ValueError('The exact originally approved Native plan is required.')
    for checked in (plan.get('requested_at'), approved.get('approved_at')):
        try:
            timestamp = datetime.fromisoformat(str(checked or ''))
        except ValueError as exc:
            raise ValueError('Historical approval timestamp is not trustworthy.') from exc
        if timestamp.tzinfo is None or timestamp > datetime.now(UTC):
            raise ValueError('Historical approval timestamp is not trustworthy.')
    if _checked_recently(plan['requested_at']) and _checked_recently(approved['approved_at']):
        raise ValueError('A current plan cannot enter expired-plan recovery.')
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.ownership_status != 'adopted'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Native Tenant provider authority differs from the historical plan.')
    return plan


def _verify_original_provider_state(
    *, tenant_id: str, plan: dict[str, Any], actor_user_id: int,
    fresh: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fresh preflight and per-resource authoritative GET: no provider PATCH."""
    if fresh is None:
        fresh = review_tenant_release_preflight_committed(
            tenant_id=tenant_id, actor_user_id=actor_user_id,
        )
    _can_confirm_plan(fresh)
    if (
        fresh.get('tenant_id') != tenant_id
        or fresh.get('cluster_id') != plan.get('cluster_id')
        or fresh.get('generation') != plan.get('generation')
        or fresh.get('provider') != 'native_kubernetes'
        or fresh.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or fresh.get('live_provider_identity') != plan.get('provider_identity')
        or fresh.get('handoff_components') != plan.get('handoff_components')
    ):
        raise ValueError('Fresh provider identity, allocation or dependency evidence changed.')
    dry_run = _latest_native_dry_run(tenant_id)
    selected = [
        row for row in plan.get('handoff_components', [])
        if row.get('handoff') == 'external_acceptance_required'
    ]
    snapshots = (dry_run or {}).get('previewed_components')
    if (
        not dry_run or dry_run.get('plan_sha256') != plan['plan_sha256']
        or dry_run.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or dry_run.get('status') != 'dry_run_passed'
        or dry_run.get('provider_mutation_performed') is not False
        or dry_run.get('release_authorized') is not False
        or not isinstance(snapshots, list)
        or not 0 < len(snapshots) <= 100
        or len(snapshots) != len(selected)
        or dry_run.get('expected_component_count') != len(snapshots)
        or len({_component_key(row) for row in snapshots}) != len(snapshots)
    ):
        raise ValueError('Exact historical no-mutation preview is unavailable.')
    for preview in snapshots:
        _approved_component_for_preview(plan=plan, preview=preview)
    cluster = db.session.get(Cluster, plan['cluster_id'])
    if cluster is None:
        raise ValueError('Registered Native provider connection is unavailable.')
    if getattr(getattr(cluster, 'kubernetes_connection', None), 'verify_ssl', None) is not True:
        raise ValueError('Verified Kubernetes API TLS is required for authoritative recovery.')
    try:
        core = runtime_adapter.build_client(cluster).core_api()
        live = {_component_key(row): _read_resource(core, row) for row in snapshots}
        proof = summarize_native_handoff_recovery(
            previewed_components=snapshots, live_components=live,
            tenant_id=tenant_id, successor_owner=plan['successor_owner'],
        )
    except (ApiException, ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Authoritative provider ownership, UID/RV or retained metadata differs.') from exc
    if (
        proof.get('status') != 'provider_handoff_not_started'
        or proof.get('transferred_count') != 0
        or proof.get('pending_count') != len(snapshots)
        or proof.get('provider_spec_preserved') is not True
        or proof.get('provider_resource_deleted') is not False
        or proof.get('release_authorized') is not False
    ):
        raise ValueError('Partial/unknown provider transfer requires independent recovery investigation.')
    return {
        'provider_proof_sha256': _sha(proof),
        'observed_components': proof['components'],
        'verified_count': len(proof['components']),
    }


def assess_native_no_transfer_recovery_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """Requester explicitly assesses a failed-before-write plan via GET-only provider proof."""
    if not confirmed:
        raise ValueError('Explicit read-only recovery assessment confirmation is required.')
    plan = _require_expired_plan(tenant_id, plan_sha256)
    if actor_user_id != plan['requested_by']:
        raise ValueError('Only the original requester may initiate no-transfer recovery assessment.')
    history = _source_history(tenant_id, plan)
    proof = _verify_original_provider_state(
        tenant_id=tenant_id, plan=plan, actor_user_id=actor_user_id,
    )
    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        tenant is None or tenant.generation != plan['generation']
        or latest_release_handoff_plan(tenant_id).get('plan_sha256') != plan_sha256
        or _source_history(tenant_id, plan)['digest'] != history['digest']
    ):
        raise ValueError('Concurrent provider history or Tenant state changed during assessment.')
    receipt = {
        'status': 'verified_no_transfer_pending_independent_review',
        'tenant_id': tenant_id, 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'assessed_by': actor_user_id, 'executor_actor_id': history['executor_actor_id'],
        'failed_event_id': history['failed_event_id'],
        'history_digest': history['digest'],
        'provider_proof_sha256': proof['provider_proof_sha256'],
        'observed_components': proof['observed_components'],
        'assessed_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': False, 'release_authorized': False,
        'provider_handoff_verified': False, 'secret_material_persisted': False,
    }
    receipt['assessment_sha256'] = _sha(receipt)
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_ASSESS_TARGET, target_id=tenant_id,
        action='tenant.release.native_no_transfer_assessed',
        summary='Recorded authoritative, read-only no-transfer recovery assessment.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt


def authorize_native_no_transfer_recovery_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    assessment_sha256: str, confirmed: bool,
) -> dict[str, Any]:
    """Independent third-party decision: neither requester, assessor nor executor."""
    if not confirmed:
        raise ValueError('Explicit independent recovery authorization is required.')
    plan = _require_expired_plan(tenant_id, plan_sha256)
    assessed = latest_no_transfer_assessment(tenant_id)
    if (
        not assessed
        or assessed.get('status') != 'verified_no_transfer_pending_independent_review'
        or assessed.get('plan_sha256') != plan_sha256
        or assessed.get('handoff_fingerprint') != plan['handoff_fingerprint']
        or assessed.get('assessment_sha256') != assessment_sha256
        or _sha({k: v for k, v in assessed.items() if k != 'assessment_sha256'}) != assessment_sha256
        or not _checked_recently(assessed.get('assessed_at'))
    ):
        raise ValueError('Current exact provider recovery assessment is required.')
    if actor_user_id in {
        plan['requested_by'], assessed['assessed_by'], assessed['executor_actor_id'],
    }:
        raise ValueError('Independent recovery reviewer must differ from requester, assessor and executor.')
    if _source_history(tenant_id, plan)['digest'] != assessed['history_digest']:
        raise ValueError('Provider execution/read-back history changed after assessment.')
    existing = latest_no_transfer_decision(tenant_id)
    if existing and existing.get('assessment_sha256') == assessment_sha256:
        raise ValueError('This recovery assessment already received an independent decision.')
    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if tenant is None or tenant.generation != plan['generation']:
        raise ValueError('Tenant changed during recovery authorization.')
    if latest_no_transfer_assessment(tenant_id).get('assessment_sha256') != assessment_sha256:
        raise ValueError('A newer recovery assessment replaced the reviewed evidence.')
    if _source_history(tenant_id, plan)['digest'] != assessed['history_digest']:
        raise ValueError('Provider history changed during independent recovery decision.')
    if latest_no_transfer_decision(tenant_id) and (
        latest_no_transfer_decision(tenant_id).get('assessment_sha256') == assessment_sha256
    ):
        raise ValueError('A concurrent reviewer already decided this recovery assessment.')
    receipt = {
        'status': 'authorized_for_requester_restart',
        'tenant_id': tenant_id, 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'plan_sha256': plan_sha256,
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'assessment_sha256': assessment_sha256,
        'history_digest': assessed['history_digest'],
        'provider_proof_sha256': assessed['provider_proof_sha256'],
        'assessed_by': assessed['assessed_by'],
        'executor_actor_id': assessed['executor_actor_id'],
        'authorized_by': actor_user_id,
        'authorized_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': False, 'release_authorized': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_DECISION_TARGET, target_id=tenant_id,
        action='tenant.release.native_no_transfer_authorized',
        summary='Independently authorized a fresh requester restart, not provider transfer.',
        metadata_json=receipt,
    ))
    db.session.commit()
    return receipt


def require_authorized_no_transfer_restart(
    *, tenant_id: str, plan: dict[str, Any], actor_user_id: int,
) -> dict[str, Any]:
    """Admission helper, always revalidate provider history; never trust UI hints."""
    assessed = latest_no_transfer_assessment(tenant_id)
    decision = latest_no_transfer_decision(tenant_id)
    if (
        actor_user_id != plan['requested_by']
        or not assessed or not decision
        or assessed.get('status') != 'verified_no_transfer_pending_independent_review'
        or decision.get('status') != 'authorized_for_requester_restart'
        or assessed.get('plan_sha256') != plan['plan_sha256']
        or decision.get('plan_sha256') != plan['plan_sha256']
        or assessed.get('handoff_fingerprint') != plan['handoff_fingerprint']
        or decision.get('handoff_fingerprint') != plan['handoff_fingerprint']
        or assessed.get('assessment_sha256') != decision.get('assessment_sha256')
        or _sha({k: v for k, v in assessed.items() if k != 'assessment_sha256'}) != assessed.get('assessment_sha256')
        or decision.get('history_digest') != assessed.get('history_digest')
        or decision.get('provider_proof_sha256') != assessed.get('provider_proof_sha256')
        or decision.get('assessed_by') != plan['requested_by']
        or decision.get('authorized_by') in {
            plan['requested_by'], assessed.get('executor_actor_id'),
        }
        or not _checked_recently(assessed.get('assessed_at'))
        or not _checked_recently(decision.get('authorized_at'))
    ):
        raise ValueError('Independent no-transfer recovery authorization is absent or expired.')
    history = _source_history(tenant_id, plan)
    if (
        history['digest'] != assessed.get('history_digest')
        or history['executor_actor_id'] != assessed.get('executor_actor_id')
        or history['failed_event_id'] != assessed.get('failed_event_id')
    ):
        raise ValueError('Provider execution evidence changed; recovery authorization is invalid.')
    return decision
