from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.domain_exposure import (
    evaluate_ingress_hosts,
    evaluate_service_exposure,
    normalize_domain_pattern,
    require_policy_enforcement_capability,
    reservations_conflict,
)
from app.models import AuditEvent, User
from app.models.tenant import Tenant, TenantEnvironment, TenantNamespace
from app.models.tenant_policy import (
    TenantDomainReservation,
    TenantDomainReservationStatus,
    TenantExposurePolicy,
    TenantExposurePolicyStatus,
)


class TenantPolicyStateConflictError(RuntimeError):
    """Committed Tenant policy state changed while a mutation was applying."""


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
    event.target_type = 'tenant_policy'
    event.target_id = target_id
    event.action = action
    event.summary = summary
    event.metadata_json = metadata
    db.session.add(event)


def create_domain_reservation_committed(
    *,
    environment_id: int,
    hostname_pattern: str,
    match_mode: str = 'exact',
    actor: User | None = None,
) -> TenantDomainReservation:
    environment = db.session.get(TenantEnvironment, environment_id)
    if environment is None:
        raise ValueError('Select a Tenant environment.')
    normalized = normalize_domain_pattern(hostname_pattern, match_mode)

    candidate = TenantDomainReservation()
    candidate.public_id = str(uuid.uuid4())
    candidate.tenant_id = environment.tenant_id
    candidate.environment = environment
    candidate.hostname_pattern = normalized
    candidate.match_mode = match_mode
    candidate.status = TenantDomainReservationStatus.ACTIVE.value

    existing = (
        TenantDomainReservation.query.join(Tenant, Tenant.id == TenantDomainReservation.tenant_id)
        .filter(
            Tenant.cluster_id == environment.tenant.cluster_id,
            TenantDomainReservation.status == TenantDomainReservationStatus.ACTIVE.value,
        )
        .all()
    )
    conflict = next((item for item in existing if reservations_conflict(candidate, item)), None)
    if conflict is not None:
        raise ValueError('Hostname reservation conflicts with an active reservation on this cluster.')

    db.session.add(candidate)
    try:
        db.session.flush()
        _record_event(
            actor=actor,
            target_id=candidate.public_id,
            action='tenant.domain_reservation.created',
            summary='Tenant hostname reservation was created.',
            metadata={
                'tenant_id': candidate.tenant_id,
                'environment_id': environment.id,
                'hostname_pattern': candidate.hostname_pattern,
                'match_mode': candidate.match_mode,
                'status': candidate.status,
            },
        )
        db.session.commit()
        return candidate
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantPolicyStateConflictError('Committed hostname ownership changed. Refresh and retry.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def revoke_domain_reservation_committed(
    *,
    reservation_id: int,
    actor: User | None = None,
) -> TenantDomainReservation:
    reservation = db.session.get(TenantDomainReservation, reservation_id)
    if reservation is None:
        raise ValueError('Selected hostname reservation no longer exists.')
    reservation.status = TenantDomainReservationStatus.REVOKED.value
    _record_event(
        actor=actor,
        target_id=reservation.public_id,
        action='tenant.domain_reservation.revoked',
        summary='Tenant hostname reservation was revoked.',
        metadata={
            'tenant_id': reservation.tenant_id,
            'environment_id': reservation.tenant_environment_id,
            'hostname_pattern': reservation.hostname_pattern,
            'match_mode': reservation.match_mode,
            'status': reservation.status,
        },
    )
    db.session.commit()
    return reservation


def create_exposure_policy_committed(
    *,
    namespace_id: int,
    profile_key: str = 'ingress_only',
    allow_cluster_ip: bool | None = None,
    allow_ingress: bool | None = None,
    allow_node_port: bool | None = None,
    allow_load_balancer: bool | None = None,
    allow_external_name: bool | None = None,
    actor: User | None = None,
) -> TenantExposurePolicy:
    namespace = db.session.get(TenantNamespace, namespace_id)
    if namespace is None:
        raise ValueError('Select a Tenant namespace.')
    if TenantExposurePolicy.query.filter_by(tenant_namespace_id=namespace.id).first() is not None:
        raise ValueError('This Tenant namespace already has an exposure policy.')

    policy = TenantExposurePolicy()
    policy.public_id = str(uuid.uuid4())
    policy.tenant_id = namespace.environment.tenant_id
    policy.namespace = namespace
    policy.status = TenantExposurePolicyStatus.ACTIVE.value
    if profile_key == 'ingress_only':
        policy.profile_key = 'ingress_only'
        policy.allow_cluster_ip = True
        policy.allow_ingress = True
        policy.allow_node_port = False
        policy.allow_load_balancer = False
        policy.allow_external_name = False
    elif profile_key == 'custom':
        values = {
            'allow_cluster_ip': allow_cluster_ip,
            'allow_ingress': allow_ingress,
            'allow_node_port': allow_node_port,
            'allow_load_balancer': allow_load_balancer,
            'allow_external_name': allow_external_name,
        }
        if any(value is None for value in values.values()):
            raise ValueError('Custom exposure policy requires every exposure decision explicitly.')
        policy.profile_key = 'custom'
        for key, value in values.items():
            setattr(policy, key, bool(value))
    else:
        raise ValueError('Select a supported Tenant exposure policy profile.')

    db.session.add(policy)
    try:
        db.session.flush()
        _record_event(
            actor=actor,
            target_id=policy.public_id,
            action='tenant.exposure_policy.created',
            summary='Tenant service exposure policy was committed.',
            metadata={
                'tenant_id': policy.tenant_id,
                'namespace': namespace.namespace,
                'profile_key': policy.profile_key,
                'allow_cluster_ip': policy.allow_cluster_ip,
                'allow_ingress': policy.allow_ingress,
                'allow_node_port': policy.allow_node_port,
                'allow_load_balancer': policy.allow_load_balancer,
                'allow_external_name': policy.allow_external_name,
            },
        )
        db.session.commit()
        return policy
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantPolicyStateConflictError('Committed exposure policy changed. Refresh and retry.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise


def record_service_exposure_preflight_committed(
    *,
    policy_id: int,
    service_type: str,
    enforcement_required: bool,
    admission_ready: bool,
    actor: User | None = None,
):
    policy = db.session.get(TenantExposurePolicy, policy_id)
    if policy is None:
        raise ValueError('Selected Tenant exposure policy no longer exists.')
    require_policy_enforcement_capability(
        enforcement_required=enforcement_required,
        admission_ready=admission_ready,
    )
    decision = evaluate_service_exposure(policy, service_type)
    _record_event(
        actor=actor,
        target_id=policy.public_id,
        action='tenant.exposure_policy.service_preflight',
        summary='Tenant Service exposure was evaluated against committed policy.',
        metadata={
            'tenant_id': policy.tenant_id,
            'namespace_id': policy.tenant_namespace_id,
            'service_type': service_type,
            'allowed': decision.allowed,
            'findings': list(decision.findings),
            'admission_ready': admission_ready,
        },
    )
    db.session.commit()
    return decision


def record_ingress_preflight_committed(
    *,
    policy_id: int,
    hosts: list[str],
    enforcement_required: bool,
    admission_ready: bool,
    actor: User | None = None,
):
    policy = db.session.get(TenantExposurePolicy, policy_id)
    if policy is None:
        raise ValueError('Selected Tenant exposure policy no longer exists.')
    if not policy.allow_ingress:
        raise ValueError('Ingress is disabled by the committed Tenant exposure policy.')
    require_policy_enforcement_capability(
        enforcement_required=enforcement_required,
        admission_ready=admission_ready,
    )
    environment = policy.namespace.environment
    reservations = TenantDomainReservation.query.filter_by(
        tenant_id=policy.tenant_id,
        tenant_environment_id=environment.id,
        status=TenantDomainReservationStatus.ACTIVE.value,
    ).all()
    decision = evaluate_ingress_hosts(
        reservations,
        environment_id=environment.id,
        hosts=hosts,
    )
    _record_event(
        actor=actor,
        target_id=policy.public_id,
        action='tenant.exposure_policy.ingress_preflight',
        summary='Tenant Ingress hostnames were evaluated against committed ownership policy.',
        metadata={
            'tenant_id': policy.tenant_id,
            'namespace_id': policy.tenant_namespace_id,
            'hosts': list(hosts),
            'allowed': decision.allowed,
            'findings': list(decision.findings),
            'admission_ready': admission_ready,
        },
    )
    db.session.commit()
    return decision
