"""Two-person governance for legacy post-Handback profile-label recovery (#1128).

Source-only implementation. No UI/route is registered; proposing and reviewing
a plan never mutates Kubernetes or the previous Release/Handback receipts.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import has_request_context
from flask_login import current_user

from app.extensions.db import db
from app.kubernetes.tenant.native_handoff_dry_run import _stable_sha256
from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
from app.kubernetes.tenant.native_residual_recovery_assessment import (
    assess_legacy_native_profile_residue_readonly,
)
from app.kubernetes.tenant.release_handoff_approval import (
    _checked_recently, _valid_reference,
)
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantLifecycleStatus

_PLAN_TARGET = 'kubernetes_tenant_native_residual_cleanup_plan'
_APPROVAL_TARGET = 'kubernetes_tenant_native_residual_cleanup_approval'
_EXECUTION_TARGET = 'kubernetes_tenant_native_residual_cleanup_execution'


def _latest(tenant_id: str, target: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=target, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(event.metadata_json or {}) if event else None


def require_authenticated_recovery_actor(actor_user_id: int) -> None:
    """Approval identities must be authenticated humans, never shell IDs."""
    if not has_request_context() or not current_user.is_authenticated:
        raise ValueError('Trusted authenticated Platform Admin request is required.')
    if int(current_user.id) != actor_user_id:
        raise ValueError('Authenticated recovery actor identity mismatch.')


def latest_native_residual_cleanup_plan(tenant_id: str) -> dict[str, Any] | None:
    return _latest(tenant_id, _PLAN_TARGET)


def latest_native_residual_cleanup_approval(tenant_id: str) -> dict[str, Any] | None:
    return _latest(tenant_id, _APPROVAL_TARGET)


def latest_native_residual_cleanup_execution(tenant_id: str) -> dict[str, Any] | None:
    return _latest(tenant_id, _EXECUTION_TARGET)


def _candidate_digest(assessment: dict[str, Any]) -> str:
    if (
        assessment.get('status') != 'read_only_recovery_candidate'
        or assessment.get('provider_identity_verified') is not True
        or assessment.get('historical_spec_and_foreign_metadata_verified') is not True
        or assessment.get('cleanup_authorized') is not False
        or assessment.get('re_adopt_admitted') is not False
        or assessment.get('provider_mutation_performed') is not False
        or not isinstance(assessment.get('components'), list)
        or not 0 < len(assessment['components']) <= 100
        or assessment.get('component_count') != len(assessment['components'])
        or not 0 < assessment.get('residual_component_count', 0) <= len(assessment['components'])
    ):
        raise ValueError('Exact read-only legacy recovery candidate evidence is required.')
    return _stable_sha256({
        'tenant_id': assessment['tenant_id'],
        'cluster_id': assessment['cluster_id'],
        'generation': assessment['generation'],
        'release_plan_sha256': assessment['release_plan_sha256'],
        'historical_handback_plan_sha256': assessment['historical_handback_plan_sha256'],
        'successor_owner': assessment['successor_owner'],
        'components': assessment['components'],
    })


def _require_plan(tenant_id: str, plan_sha256: str) -> dict[str, Any]:
    plan = latest_native_residual_cleanup_plan(tenant_id)
    if (
        not plan or plan.get('status') != 'pending_independent_review'
        or plan.get('tenant_id') != tenant_id
        or plan.get('plan_sha256') != plan_sha256
        or not _checked_recently(plan.get('requested_at'))
        or not isinstance(plan.get('requested_by'), int)
        or plan.get('requested_by') < 1
        or _stable_sha256({key: value for key, value in plan.items()
                        if key != 'plan_sha256'}) != plan_sha256
    ):
        raise ValueError('Current unexpired immutable residual recovery plan is required.')
    return plan


def prepare_native_residual_cleanup_committed(
    *, tenant_id: str, actor_user_id: int, change_reference: str,
    confirmed: bool,
) -> dict[str, Any]:
    """Requester records a bounded read-only plan, never provider execution."""
    if not confirmed:
        raise ValueError('Explicit recovery planning confirmation is required.')
    require_authenticated_recovery_actor(actor_user_id)
    require_platform_admin_actor(actor_user_id)
    reference = _valid_reference(change_reference, name='Recovery change reference')
    if latest_native_residual_cleanup_plan(tenant_id) or latest_native_residual_cleanup_execution(tenant_id):
        raise ValueError('Existing recovery plan/history requires explicit human review, not automatic restart.')
    assessed = assess_legacy_native_profile_residue_readonly(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    digest = _candidate_digest(assessed)
    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or tenant.cluster_id != assessed['cluster_id']
        or tenant.generation != assessed['generation']
        or latest_native_residual_cleanup_plan(tenant_id)
        or latest_native_residual_cleanup_execution(tenant_id)
    ):
        raise ValueError('Concurrent Released lineage or recovery plan changed.')
    record = {
        'status': 'pending_independent_review',
        'tenant_id': tenant_id, 'cluster_id': assessed['cluster_id'],
        'generation': assessed['generation'],
        'release_plan_sha256': assessed['release_plan_sha256'],
        'handback_plan_sha256': assessed['historical_handback_plan_sha256'],
        'successor_owner': assessed['successor_owner'],
        'candidate_digest_sha256': digest,
        'components': assessed['components'],
        'residual_component_count': assessed['residual_component_count'],
        'change_reference': reference,
        'requested_by': actor_user_id,
        'requested_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': False,
        'execution_authorized': False,
        're_adopt_admitted': False,
    }
    record['plan_sha256'] = _stable_sha256(record)
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_PLAN_TARGET, target_id=tenant_id,
        action='tenant.release.native_residual_cleanup_planned',
        summary='Read-only legacy Native cleanup plan awaiting independent approval.',
        metadata_json=record,
    ))
    db.session.commit()
    return record


def approve_native_residual_cleanup_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str,
    confirmed: bool,
) -> dict[str, Any]:
    """Independent Platform Admin approves exact unchanged provider evidence."""
    if not confirmed:
        raise ValueError('Explicit independent recovery approval is required.')
    require_authenticated_recovery_actor(actor_user_id)
    require_platform_admin_actor(actor_user_id)
    plan = _require_plan(tenant_id, plan_sha256)
    if actor_user_id == plan['requested_by']:
        raise ValueError('Recovery reviewer must differ from the requester.')
    if latest_native_residual_cleanup_approval(tenant_id) or latest_native_residual_cleanup_execution(tenant_id):
        raise ValueError('Recovery decision/execution already exists; no approval replay.')
    assessed = assess_legacy_native_profile_residue_readonly(
        tenant_id=tenant_id, actor_user_id=actor_user_id,
    )
    if (
        assessed.get('tenant_id') != tenant_id
        or assessed.get('cluster_id') != plan['cluster_id']
        or assessed.get('generation') != plan['generation']
        or _candidate_digest(assessed) != plan['candidate_digest_sha256']
    ):
        raise ValueError('Provider recovery evidence changed since requester plan.')
    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.RELEASED.value
        or tenant.generation != plan['generation']
        or latest_native_residual_cleanup_approval(tenant_id)
        or latest_native_residual_cleanup_execution(tenant_id)
        or _require_plan(tenant_id, plan_sha256) != plan
    ):
        raise ValueError('Concurrent recovery decision or Released lineage changed.')
    decision = {
        'status': 'approved_for_exact_metadata_cleanup',
        'tenant_id': tenant_id, 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'],
        'plan_sha256': plan_sha256,
        'candidate_digest_sha256': plan['candidate_digest_sha256'],
        'release_plan_sha256': plan['release_plan_sha256'],
        'handback_plan_sha256': plan['handback_plan_sha256'],
        'requested_by': plan['requested_by'],
        'approved_by': actor_user_id,
        'approved_at': datetime.now(UTC).isoformat(),
        'provider_mutation_performed': False,
        'execution_performed': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_APPROVAL_TARGET, target_id=tenant_id,
        action='tenant.release.native_residual_cleanup_independently_approved',
        summary='Independent review approved exact residual metadata scope; not executed.',
        metadata_json=decision,
    ))
    db.session.commit()
    return decision
