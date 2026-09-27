from __future__ import annotations

import uuid
from copy import deepcopy

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.capsule_advanced import (
    capsule_resource_descriptor,
    reconcile_capsule_advanced_intent,
    remove_capsule_advanced_intent,
)
from app.kubernetes.tenant.capsule_provider import CapsuleDiscoverySnapshot, CapsuleTenantProvider
from app.kubernetes.tenant.providers import TenantCapabilityStatus
from app.models import AuditEvent, User
from app.models.tenant import Tenant, TenantNamespace
from app.models.tenant_advanced import (
    TenantAdvancedCapabilityIntent,
    TenantAdvancedCapabilityStatus,
)


class TenantAdvancedCapabilityStateConflictError(RuntimeError):
    """Committed advanced capability state changed while a mutation was applying."""


def _provider_from_committed_evidence(tenant: Tenant) -> CapsuleTenantProvider:
    evidence = tenant.provider_evidence_json or {}
    capsule = evidence.get('capsule')
    if not isinstance(capsule, dict):
        raise ValueError('Committed Capsule discovery evidence is required before advanced capability execution.')

    raw_capabilities = capsule.get('capabilities')
    if not isinstance(raw_capabilities, dict):
        raise ValueError('Committed Capsule capability evidence is missing.')
    capabilities: dict[str, TenantCapabilityStatus] = {}
    for key, value in raw_capabilities.items():
        try:
            capabilities[str(key)] = TenantCapabilityStatus(str(value))
        except ValueError:
            capabilities[str(key)] = TenantCapabilityStatus.UNAVAILABLE

    raw_versions = capsule.get('tenant_api_versions')
    versions = tuple(str(value) for value in raw_versions) if isinstance(raw_versions, list) else ()
    raw_crds = capsule.get('crds')
    crds = tuple(str(value) for value in raw_crds) if isinstance(raw_crds, list) else ()
    snapshot = CapsuleDiscoverySnapshot(
        installed=bool(capsule.get('installed')),
        reported_version=str(capsule.get('reported_version') or '') or None,
        tenant_api_versions=versions,
        crds=crds,
        capabilities=capabilities,
    )
    return CapsuleTenantProvider(snapshot=snapshot)


def _record_event(
    *,
    actor: User | None,
    intent: TenantAdvancedCapabilityIntent,
    action: str,
    summary: str,
    outcome: str,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_advanced_capability'
    event.target_id = intent.public_id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        'tenant_id': intent.tenant_id,
        'namespace_id': intent.tenant_namespace_id,
        'provider_key': intent.provider_key,
        'capability_key': intent.capability_key,
        'resource_kind': intent.resource_kind,
        'resource_name': intent.resource_name,
        'status': intent.status,
        'generation': intent.generation,
        'outcome': outcome,
        'correlation_id': intent.correlation_id,
        'secret_material_persisted': False,
    }
    db.session.add(event)


def create_advanced_intent_committed(
    *,
    tenant_id: str,
    resource_kind: str,
    resource_name: str,
    desired_spec: dict[str, object],
    namespace_id: int | None = None,
    actor: User | None = None,
) -> TenantAdvancedCapabilityIntent:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')
    if tenant.provider_key != 'capsule' or tenant.provider_state != 'capsule':
        raise ValueError('Advanced Capsule capability requires healthy Capsule provider authority.')

    namespace = db.session.get(TenantNamespace, namespace_id) if namespace_id is not None else None
    if namespace is not None and namespace.environment.tenant_id != tenant.id:
        raise ValueError('Selected namespace belongs to another Tenant.')

    descriptor = capsule_resource_descriptor(resource_kind)
    name = resource_name.strip()
    if not name:
        raise ValueError('Advanced Capsule resource name is required.')
    existing = TenantAdvancedCapabilityIntent.query.filter_by(
        tenant_id=tenant.id,
        tenant_namespace_id=namespace.id if namespace is not None else None,
        resource_kind=resource_kind,
        resource_name=name,
        status=TenantAdvancedCapabilityStatus.READY.value,
    ).first()
    if existing is not None:
        raise ValueError('An active advanced Capsule intent already owns this resource.')

    intent = TenantAdvancedCapabilityIntent()
    intent.public_id = str(uuid.uuid4())
    intent.tenant = tenant
    intent.namespace = namespace
    intent.provider_key = 'capsule'
    intent.capability_key = descriptor.capability
    intent.resource_kind = resource_kind
    intent.resource_name = name
    intent.provider_api_version = 'v1beta2'
    intent.desired_spec_json = deepcopy(desired_spec)
    intent.status = TenantAdvancedCapabilityStatus.PENDING.value
    intent.generation = 1
    db.session.add(intent)

    try:
        db.session.flush()
        provider = _provider_from_committed_evidence(tenant)
        reconcile_capsule_advanced_intent(intent, provider=provider)
        _record_event(
            actor=actor,
            intent=intent,
            action='tenant.advanced_capability.created',
            summary='Advanced Capsule capability intent was committed and reconciled.',
            outcome='success',
        )
        db.session.commit()
        return intent
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantAdvancedCapabilityStateConflictError(
            'Committed advanced Capsule capability state changed. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def reconcile_advanced_intent_committed(
    *,
    intent_id: int,
    desired_spec: dict[str, object] | None = None,
    actor: User | None = None,
) -> TenantAdvancedCapabilityIntent:
    intent = db.session.get(TenantAdvancedCapabilityIntent, intent_id)
    if intent is None:
        raise ValueError('Selected advanced Capsule intent no longer exists.')
    if desired_spec is not None:
        intent.desired_spec_json = deepcopy(desired_spec)
        intent.generation += 1
        intent.status = TenantAdvancedCapabilityStatus.PENDING.value
    try:
        provider = _provider_from_committed_evidence(intent.tenant)
        reconcile_capsule_advanced_intent(intent, provider=provider)
        _record_event(
            actor=actor,
            intent=intent,
            action='tenant.advanced_capability.reconciled',
            summary='Advanced Capsule capability intent was reconciled against effective provider state.',
            outcome='success',
        )
        db.session.commit()
        return intent
    except (ApiException, ValueError):
        db.session.rollback()
        raise


def remove_advanced_intent_committed(
    *,
    intent_id: int,
    actor: User | None = None,
) -> TenantAdvancedCapabilityIntent:
    intent = db.session.get(TenantAdvancedCapabilityIntent, intent_id)
    if intent is None:
        raise ValueError('Selected advanced Capsule intent no longer exists.')
    try:
        provider = _provider_from_committed_evidence(intent.tenant)
        remove_capsule_advanced_intent(intent, provider=provider)
        _record_event(
            actor=actor,
            intent=intent,
            action='tenant.advanced_capability.removed',
            summary='Advanced Capsule capability intent was disabled and effective provider state removed or reset.',
            outcome='success',
        )
        db.session.commit()
        return intent
    except (ApiException, ValueError):
        db.session.rollback()
        raise
