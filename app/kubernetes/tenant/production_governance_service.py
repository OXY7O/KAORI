from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.extensions.db import db
from app.kubernetes.tenant.access_reconciliation import target_namespaces
from app.kubernetes.tenant.production_governance import (
    effective_production_exception_status,
    evaluate_production_access,
    is_production_namespace,
)
from app.models import AuditEvent, User
from app.models.tenant import (
    TenantAccessGrant,
    TenantAccessGrantStatus,
    TenantCredential,
    TenantNamespace,
    TenantProductionAccessException,
    TenantProductionAccessExceptionStatus,
)

DEFAULT_PRODUCTION_EXCEPTION_HOURS = 8
MAX_PRODUCTION_EXCEPTION_HOURS = 168


def _now() -> datetime:
    return datetime.now(UTC)


def _record_event(
    *,
    actor: User | None,
    target_id: str,
    action: str,
    summary: str,
    metadata: dict[str, object],
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_production_access'
    event.target_id = target_id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        **metadata,
        'secret_material_persisted': False,
    }
    db.session.add(event)


def create_production_access_exception_committed(
    *,
    namespace_id: int,
    access_grant_id: int,
    owner_user_id: int,
    approved_by_user_id: int,
    reason: str,
    validity_hours: int = DEFAULT_PRODUCTION_EXCEPTION_HOURS,
    actor: User | None = None,
) -> TenantProductionAccessException:
    namespace = db.session.get(TenantNamespace, namespace_id)
    grant = db.session.get(TenantAccessGrant, access_grant_id)
    owner = db.session.get(User, owner_user_id)
    approver = db.session.get(User, approved_by_user_id)

    if namespace is None or not is_production_namespace(namespace):
        raise ValueError('Production access exception requires a production Tenant namespace.')
    if grant is None or grant.status != TenantAccessGrantStatus.ACTIVE.value:
        raise ValueError('Production access exception requires an active Tenant Access Grant.')
    if owner is None or not owner.is_active:
        raise ValueError('Production access exception requires an active owner.')
    if approver is None or not approver.is_active or not approver.is_admin_level:
        raise ValueError('Production access exception requires approval by an active KAORI administrator.')
    if grant.membership.principal_type != 'user' or grant.membership.user_id != owner.id:
        raise ValueError('Production access exception must be owned by the human principal on the Access Grant.')
    if grant.access_profile == 'deployer':
        raise ValueError('Production Deployer access is pipeline authority and cannot use a human exception.')
    if namespace.id not in {item.id for item in target_namespaces(grant)}:
        raise ValueError('Production access exception namespace is outside the selected Access Grant scope.')

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError('Production access exception requires an operator reason.')
    hours = int(validity_hours)
    if hours < 1 or hours > MAX_PRODUCTION_EXCEPTION_HOURS:
        raise ValueError(
            f'Production access exception validity must be between 1 and {MAX_PRODUCTION_EXCEPTION_HOURS} hours.'
        )

    started = _now()
    valid_until = started + timedelta(hours=hours)
    exception = TenantProductionAccessException()
    exception.public_id = str(uuid.uuid4())
    exception.tenant_id = namespace.environment.tenant_id
    exception.namespace = namespace
    exception.access_grant = grant
    exception.owner_user = owner
    exception.approved_by_user = approver
    exception.reason = normalized_reason
    exception.status = TenantProductionAccessExceptionStatus.ACTIVE.value
    exception.valid_from = started
    exception.review_due_at = valid_until
    exception.valid_until = valid_until
    db.session.add(exception)
    db.session.flush()

    _record_event(
        actor=actor,
        target_id=exception.public_id,
        action='tenant.production_access_exception.created',
        summary='Bounded production human-access exception was approved.',
        metadata={
            'tenant_id': exception.tenant_id,
            'namespace': namespace.namespace,
            'access_grant_id': grant.public_id,
            'owner_user_id': owner.id,
            'approved_by_user_id': approver.id,
            'valid_until': valid_until.isoformat(),
            'status': exception.status,
        },
    )
    db.session.commit()
    return exception


def revoke_production_access_exception_committed(
    *,
    exception_id: int,
    actor: User | None = None,
) -> TenantProductionAccessException:
    exception = db.session.get(TenantProductionAccessException, exception_id)
    if exception is None:
        raise ValueError('Selected production access exception no longer exists.')
    if exception.status == TenantProductionAccessExceptionStatus.REVOKED.value:
        return exception

    exception.status = TenantProductionAccessExceptionStatus.REVOKED.value
    _record_event(
        actor=actor,
        target_id=exception.public_id,
        action='tenant.production_access_exception.revoked',
        summary='Production human-access exception was revoked.',
        metadata={
            'tenant_id': exception.tenant_id,
            'namespace_id': exception.tenant_namespace_id,
            'owner_user_id': exception.owner_user_id,
            'status': exception.status,
        },
    )
    db.session.commit()
    return exception


def enforce_production_access_exception_lifecycle_committed(
    *,
    exception_id: int,
    actor: User | None = None,
) -> TenantProductionAccessException:
    exception = db.session.get(TenantProductionAccessException, exception_id)
    if exception is None:
        raise ValueError('Selected production access exception no longer exists.')
    effective = effective_production_exception_status(exception)
    if effective == TenantProductionAccessExceptionStatus.EXPIRED.value and exception.status != effective:
        exception.status = effective
        _record_event(
            actor=actor,
            target_id=exception.public_id,
            action='tenant.production_access_exception.expired',
            summary='Production human-access exception expired.',
            metadata={
                'tenant_id': exception.tenant_id,
                'namespace_id': exception.tenant_namespace_id,
                'owner_user_id': exception.owner_user_id,
                'status': exception.status,
            },
        )
        db.session.commit()
    return exception


def record_production_access_decision_committed(
    *,
    credential_id: int,
    namespace_id: int,
    verb: str,
    resource_kind: str,
    resource_name: str | None = None,
    exception_id: int | None = None,
    actor: User | None = None,
):
    credential = db.session.get(TenantCredential, credential_id)
    namespace = db.session.get(TenantNamespace, namespace_id)
    exception = db.session.get(TenantProductionAccessException, exception_id) if exception_id is not None else None
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')
    if namespace is None:
        raise ValueError('Selected Tenant namespace no longer exists.')

    decision = evaluate_production_access(
        credential,
        namespace,
        verb=verb,
        exception=exception,
    )
    _record_event(
        actor=actor,
        target_id=credential.public_id,
        action='tenant.production_access_decision',
        summary='Production access decision was evaluated against pipeline-first Tenant governance.',
        metadata={
            'tenant_id': credential.tenant_id,
            'namespace': namespace.namespace,
            'credential_id': credential.public_id,
            'credential_type': credential.credential_type,
            'verb': verb.strip().lower(),
            'resource_kind': resource_kind,
            'resource_name': resource_name,
            'allowed': decision.allowed,
            'compliant': decision.compliant,
            'authority': decision.authority,
            'findings': list(decision.findings),
            'exception_id': getattr(exception, 'public_id', None),
        },
    )
    db.session.commit()
    return decision
