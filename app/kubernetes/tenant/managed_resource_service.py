from __future__ import annotations

import uuid

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.managed_resources import (
    ManagedResourceSecretMaterial,
    reconcile_native_managed_resource,
    remove_native_managed_resource,
)
from app.models import AuditEvent, User
from app.models.tenant import TenantNamespace, TenantNamespaceProvisioningStatus
from app.models.tenant_managed_resource import (
    TenantManagedResourceIntent,
    TenantManagedResourceKind,
    TenantManagedResourceMode,
    TenantManagedResourceStatus,
)


class TenantManagedResourceStateConflictError(RuntimeError):
    """Committed Tenant managed-resource state changed while a mutation was applying."""


def _record_event(
    *,
    actor: User | None,
    intent: TenantManagedResourceIntent,
    action: str,
    summary: str,
    outcome: str,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_managed_resource'
    event.target_id = intent.public_id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        'tenant_id': intent.tenant_id,
        'namespace_id': intent.tenant_namespace_id,
        'resource_kind': intent.resource_kind,
        'mode': intent.mode,
        'resource_name': intent.resource_name,
        'source_reference': intent.source_reference,
        'status': intent.status,
        'rotation_generation': intent.rotation_generation,
        'outcome': outcome,
        'correlation_id': intent.correlation_id,
        'secret_material_persisted': False,
    }
    db.session.add(event)


def create_managed_resource_intent_committed(
    *,
    namespace_id: int,
    resource_kind: str,
    mode: str,
    resource_name: str,
    source_reference: str | None = None,
    material: ManagedResourceSecretMaterial | None = None,
    external_provider_ready: bool = False,
    actor: User | None = None,
) -> TenantManagedResourceIntent:
    namespace = db.session.get(TenantNamespace, namespace_id)
    if namespace is None:
        raise ValueError('Select a managed Tenant namespace.')
    if namespace.provisioning_status != TenantNamespaceProvisioningStatus.READY.value:
        raise ValueError('Managed resources require a Ready Tenant namespace.')

    kind = TenantManagedResourceKind(resource_kind)
    selected_mode = TenantManagedResourceMode(mode)
    name = resource_name.strip()
    if not name:
        raise ValueError('Managed resource name is required.')
    reference = (source_reference or '').strip() or None

    existing = TenantManagedResourceIntent.query.filter_by(
        tenant_namespace_id=namespace.id,
        resource_kind=kind.value,
    ).first()
    if existing is not None:
        raise ValueError('This Tenant namespace already has a managed resource intent for the selected kind.')

    intent = TenantManagedResourceIntent()
    intent.public_id = str(uuid.uuid4())
    intent.tenant_id = namespace.environment.tenant_id
    intent.namespace = namespace
    intent.resource_kind = kind.value
    intent.mode = selected_mode.value
    intent.resource_name = name
    intent.source_reference = reference
    intent.status = TenantManagedResourceStatus.PENDING.value
    intent.rotation_generation = 1
    db.session.add(intent)

    try:
        db.session.flush()
        reconcile_native_managed_resource(
            intent,
            material=material,
            external_provider_ready=external_provider_ready,
        )
        _record_event(
            actor=actor,
            intent=intent,
            action='tenant.managed_resource.created',
            summary='Tenant managed platform-security resource intent was created and reconciled.',
            outcome='success',
        )
        db.session.commit()
        return intent
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantManagedResourceStateConflictError(
            'Committed Tenant managed-resource state changed. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def rotate_managed_resource_committed(
    *,
    intent_id: int,
    material: ManagedResourceSecretMaterial,
    source_reference: str | None = None,
    actor: User | None = None,
) -> TenantManagedResourceIntent:
    intent = db.session.get(TenantManagedResourceIntent, intent_id)
    if intent is None:
        raise ValueError('Selected Tenant managed resource no longer exists.')
    if intent.mode not in {
        TenantManagedResourceMode.NAMESPACE_TLS_COMPAT.value,
        TenantManagedResourceMode.IMAGE_PULL_SECRET.value,
    }:
        raise ValueError('Only namespace Secret compatibility modes support material rotation.')

    if source_reference is not None:
        reference = source_reference.strip()
        if not reference:
            raise ValueError('Managed resource source reference cannot be blank.')
        intent.source_reference = reference
    intent.rotation_generation += 1
    intent.status = TenantManagedResourceStatus.PENDING.value
    try:
        reconcile_native_managed_resource(intent, material=material)
        _record_event(
            actor=actor,
            intent=intent,
            action='tenant.managed_resource.rotated',
            summary='Tenant managed platform-security resource was rotated and reconciled.',
            outcome='success',
        )
        db.session.commit()
        return intent
    except (ApiException, ValueError):
        db.session.rollback()
        raise


def remove_managed_resource_committed(
    *,
    intent_id: int,
    actor: User | None = None,
) -> TenantManagedResourceIntent:
    intent = db.session.get(TenantManagedResourceIntent, intent_id)
    if intent is None:
        raise ValueError('Selected Tenant managed resource no longer exists.')
    try:
        remove_native_managed_resource(intent)
        _record_event(
            actor=actor,
            intent=intent,
            action='tenant.managed_resource.removed',
            summary='Tenant managed platform-security resource was removed from effective provider state.',
            outcome='success',
        )
        db.session.commit()
        return intent
    except (ApiException, ValueError):
        db.session.rollback()
        raise
