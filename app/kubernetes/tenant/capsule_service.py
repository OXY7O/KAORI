from __future__ import annotations

from copy import deepcopy

from app.extensions.db import db
from app.kubernetes.tenant.capsule_provider import (
    CapsuleDiscoverySnapshot,
    CapsuleTenantProvider,
    validate_native_recovery_readiness,
)
from app.kubernetes.tenant.providers import (
    ProviderAuthorityTransition,
    TenantCapabilityStatus,
    TenantProviderKey,
    TenantProviderState,
    validate_authority_transition,
)
from app.models import AuditEvent, User
from app.models.tenant import Tenant


def _record_event(
    *,
    actor: User | None,
    tenant: Tenant,
    action: str,
    summary: str,
    metadata: dict[str, object],
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_provider'
    event.target_id = tenant.id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        **metadata,
        'tenant_id': tenant.id,
        'secret_material_persisted': False,
    }
    db.session.add(event)


def _evidence(tenant: Tenant) -> dict[str, object]:
    return deepcopy(tenant.provider_evidence_json or {})


def observe_capsule_provider_committed(
    *,
    tenant_id: str,
    snapshot: CapsuleDiscoverySnapshot,
    actor: User | None = None,
) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')

    provider = CapsuleTenantProvider(snapshot=snapshot)
    result = provider.validate_binding(cluster_id=tenant.cluster_id)
    evidence = _evidence(tenant)
    evidence['capsule'] = {
        **snapshot.as_dict(),
        'provider_state': result.state.value,
    }
    tenant.provider_evidence_json = evidence

    if tenant.provider_key == TenantProviderKey.CAPSULE.value:
        tenant.provider_state = result.state.value
        tenant.reconciliation_authority = 'capsule'

    _record_event(
        actor=actor,
        tenant=tenant,
        action='tenant.provider.capsule_observed',
        summary='Capsule capability discovery was committed without implicit authority transfer.',
        metadata={
            'provider_key': tenant.provider_key,
            'provider_state': tenant.provider_state,
            'capsule_state': result.state.value,
            'capabilities': {item.key: item.status.value for item in result.capabilities},
        },
    )
    db.session.commit()
    return tenant


def begin_native_recovery_committed(
    *,
    tenant_id: str,
    snapshot: CapsuleDiscoverySnapshot,
    effective_governance_snapshot: dict[str, object],
    actor: User | None = None,
) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')
    if tenant.provider_key != TenantProviderKey.CAPSULE.value:
        raise ValueError('Native Recovery requires Capsule to be the current provider authority.')
    if tenant.provider_state != TenantProviderState.CAPSULE_DEGRADED.value:
        raise ValueError('Native Recovery may start only from Capsule Degraded state.')
    if not effective_governance_snapshot:
        raise ValueError('Native Recovery requires an effective Capsule governance snapshot.')

    evidence = _evidence(tenant)
    evidence['native_recovery'] = {
        'phase': 'snapshot',
        'capsule': snapshot.as_dict(),
        'effective_governance': deepcopy(effective_governance_snapshot),
        'verified': False,
        'authority_transferred': False,
        'secret_material_persisted': False,
    }
    tenant.provider_evidence_json = evidence
    tenant.provider_state = TenantProviderState.NATIVE_RECOVERY.value
    tenant.reconciliation_authority = 'capsule'

    _record_event(
        actor=actor,
        tenant=tenant,
        action='tenant.provider.native_recovery_started',
        summary='Native Recovery started after committing effective Capsule governance evidence.',
        metadata={
            'provider_state': tenant.provider_state,
            'reconciliation_authority': tenant.reconciliation_authority,
            'phase': 'snapshot',
        },
    )
    db.session.commit()
    return tenant


def complete_native_recovery_committed(
    *,
    tenant_id: str,
    snapshot: CapsuleDiscoverySnapshot,
    native_capabilities: dict[str, TenantCapabilityStatus],
    materialized_capabilities: set[str],
    verified: bool,
    actor: User | None = None,
) -> Tenant:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')
    if tenant.provider_key != TenantProviderKey.CAPSULE.value:
        raise ValueError('Native Recovery completion requires Capsule to remain current authority.')
    if tenant.provider_state != TenantProviderState.NATIVE_RECOVERY.value:
        raise ValueError('Tenant is not in Native Recovery state.')

    validate_native_recovery_readiness(
        snapshot=snapshot,
        native_capabilities=native_capabilities,
        materialized_capabilities=materialized_capabilities,
        verified=verified,
    )
    validate_authority_transition(
        ProviderAuthorityTransition(
            current_provider=TenantProviderKey.CAPSULE,
            target_provider=TenantProviderKey.NATIVE_KUBERNETES,
            current_state=TenantProviderState.NATIVE_RECOVERY,
            recovery_verified=verified,
        )
    )

    evidence = _evidence(tenant)
    recovery = deepcopy(evidence.get('native_recovery') or {})
    recovery.update(
        {
            'phase': 'completed',
            'native_capabilities': {key: value.value for key, value in sorted(native_capabilities.items())},
            'materialized_capabilities': sorted(materialized_capabilities),
            'verified': True,
            'authority_transferred': True,
            'secret_material_persisted': False,
        }
    )
    evidence['native_recovery'] = recovery
    tenant.provider_evidence_json = evidence
    tenant.provider_key = TenantProviderKey.NATIVE_KUBERNETES.value
    tenant.provider_state = TenantProviderState.NATIVE.value
    tenant.reconciliation_authority = 'native_kubernetes'

    _record_event(
        actor=actor,
        tenant=tenant,
        action='tenant.provider.native_recovery_completed',
        summary='Verified Native protections became the Tenant reconciliation authority.',
        metadata={
            'provider_key': tenant.provider_key,
            'provider_state': tenant.provider_state,
            'reconciliation_authority': tenant.reconciliation_authority,
            'phase': 'completed',
        },
    )
    db.session.commit()
    return tenant
