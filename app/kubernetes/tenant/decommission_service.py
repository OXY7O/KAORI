from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.access_service import (
    revoke_access_grant_committed,
    revoke_membership_committed,
)
from app.kubernetes.tenant.capsule_tenant import delete_capsule_tenant_verified
from app.kubernetes.tenant.credential_service import revoke_credential_committed
from app.kubernetes.tenant.managed_resource_service import remove_managed_resource_committed
from app.kubernetes.tenant.provisioning import deprovision_native_namespace_committed
from app.models import AuditEvent, Cluster, User
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantAccessGrantStatus,
    TenantCredential,
    TenantCredentialStatus,
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantMembership,
    TenantMembershipStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantOwnershipStatus,
)
from app.models.tenant_advanced import TenantAdvancedCapabilityIntent, TenantAdvancedCapabilityStatus
from app.models.tenant_managed_resource import TenantManagedResourceIntent, TenantManagedResourceStatus
from app.models.tenant_policy import (
    TenantDomainReservation,
    TenantDomainReservationStatus,
    TenantExposurePolicy,
    TenantExposurePolicyStatus,
)

ProgressCallback = Callable[[int, str], None]


class TenantDecommissionBlocked(RuntimeError):
    """Governed teardown cannot proceed without violating an authority boundary."""


def _now() -> datetime:
    return datetime.now(UTC)


def _record_event(
    *,
    tenant: Tenant,
    actor: User | None,
    action: str,
    summary: str,
    outcome: str,
    stage: str,
    detail: str | None = None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant'
    event.target_id = tenant.id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        'tenant_id': tenant.id,
        'tenant_slug': tenant.slug,
        'tenant_generation': tenant.generation,
        'cluster_id': tenant.cluster_id,
        'provider_key': tenant.provider_key,
        'provider_state': tenant.provider_state,
        'reconciliation_authority': tenant.reconciliation_authority,
        'lifecycle_status': tenant.lifecycle_status,
        'stage': stage,
        'outcome': outcome,
        'detail': detail,
        'correlation_id': tenant.correlation_id,
        'secret_material_persisted': False,
    }
    db.session.add(event)


def _active_credential_count(tenant_id: str) -> int:
    return TenantCredential.query.filter(
        TenantCredential.tenant_id == tenant_id,
        TenantCredential.status != TenantCredentialStatus.REVOKED.value,
    ).count()


def _active_grant_count(tenant_id: str) -> int:
    return TenantAccessGrant.query.filter_by(
        tenant_id=tenant_id,
        status=TenantAccessGrantStatus.ACTIVE.value,
    ).count()


def _active_membership_count(tenant_id: str) -> int:
    return TenantMembership.query.filter_by(
        tenant_id=tenant_id,
        status=TenantMembershipStatus.ACTIVE.value,
    ).count()


def build_tenant_decommission_preflight(tenant_id: str) -> dict[str, Any]:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant no longer exists.')

    namespaces = (
        TenantNamespace.query.join(
            TenantEnvironment,
            TenantNamespace.tenant_environment_id == TenantEnvironment.id,
        )
        .filter(TenantEnvironment.tenant_id == tenant.id)
        .order_by(TenantNamespace.namespace.asc())
        .all()
    )
    unmanaged_namespaces = [
        item.namespace
        for item in namespaces
        if item.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
        and item.ownership_status != TenantOwnershipStatus.MANAGED.value
    ]
    active_advanced = TenantAdvancedCapabilityIntent.query.filter(
        TenantAdvancedCapabilityIntent.tenant_id == tenant.id,
        TenantAdvancedCapabilityIntent.status != TenantAdvancedCapabilityStatus.DISABLED.value,
    ).count()
    credential_count = _active_credential_count(tenant.id)
    access_grant_count = _active_grant_count(tenant.id)
    membership_count = _active_membership_count(tenant.id)
    namespace_count = sum(
        1
        for item in namespaces
        if item.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
    )
    managed_resource_count = TenantManagedResourceIntent.query.filter(
        TenantManagedResourceIntent.tenant_id == tenant.id,
        TenantManagedResourceIntent.status != TenantManagedResourceStatus.DISABLED.value,
    ).count()
    provider_evidence = dict(tenant.provider_evidence_json or {})

    blockers: list[str] = []
    if tenant.lifecycle_status == TenantLifecycleStatus.DECOMMISSIONED.value:
        blockers.append('Tenant is already decommissioned.')
    elif tenant.lifecycle_status not in {
        TenantLifecycleStatus.READY.value,
        TenantLifecycleStatus.DEGRADED.value,
        TenantLifecycleStatus.DECOMMISSIONING.value,
    }:
        blockers.append(f'Tenant lifecycle {tenant.lifecycle_status!r} is not eligible for decommission.')

    if tenant.provider_key == 'capsule' or tenant.reconciliation_authority == 'capsule':
        if tenant.provider_key != 'capsule' or tenant.reconciliation_authority != 'capsule':
            blockers.append('Capsule teardown requires committed Capsule provider and reconciliation authority.')
        elif tenant.provider_state != 'capsule':
            blockers.append('Capsule provider is degraded; teardown fails closed until authority is healthy.')
        if tenant.ownership_status != TenantOwnershipStatus.MANAGED.value or not bool(
            provider_evidence.get('created_by_kaori')
        ):
            blockers.append(
                'Baseline Capsule teardown is limited to KAORI-created managed Tenant CRs; '
                'adopted/foreign provider objects remain fail-closed.'
            )
        if not str(provider_evidence.get('provider_api_version') or '').strip():
            blockers.append('Capsule teardown requires committed provider API-version evidence.')
        if not str(provider_evidence.get('provider_reference') or tenant.provider_reference or '').strip():
            blockers.append('Capsule teardown requires a committed provider reference.')
        if namespace_count:
            blockers.append(
                'Baseline Capsule teardown requires zero active Tenant namespace records; '
                'Capsule namespace teardown is not admitted in this slice.'
            )
        if access_grant_count or credential_count:
            blockers.append(
                'Baseline Capsule teardown requires active Access Grants and credentials to be cleared '
                'through an admitted provider path first.'
            )
        if managed_resource_count:
            blockers.append(
                'Baseline Capsule teardown requires Tenant-managed provider resources to be cleared first.'
            )
    elif (
        tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
    ):
        blockers.append('Native Kubernetes teardown requires committed Native provider and reconciliation authority.')

    if unmanaged_namespaces:
        blockers.append(
            'Automatic teardown is limited to KAORI-managed namespaces. Resolve ownership first: '
            + ', '.join(unmanaged_namespaces)
        )
    if active_advanced:
        blockers.append(
            'Active Capsule advanced capability intents remain. Remove them through Capsule authority before teardown.'
        )

    return {
        'tenant': tenant,
        'tenant_id': tenant.id,
        'tenant_name': tenant.name,
        'tenant_slug': tenant.slug,
        'tenant_generation': tenant.generation,
        'cluster_id': tenant.cluster_id,
        'provider_key': tenant.provider_key,
        'provider_state': tenant.provider_state,
        'reconciliation_authority': tenant.reconciliation_authority,
        'lifecycle_status': tenant.lifecycle_status,
        'credential_count': credential_count,
        'access_grant_count': access_grant_count,
        'membership_count': membership_count,
        'group_count': sum(1 for item in tenant.groups if item.enabled),
        'namespace_count': namespace_count,
        'managed_resource_count': managed_resource_count,
        'domain_reservation_count': TenantDomainReservation.query.filter_by(
            tenant_id=tenant.id,
            status=TenantDomainReservationStatus.ACTIVE.value,
        ).count(),
        'exposure_policy_count': TenantExposurePolicy.query.filter_by(
            tenant_id=tenant.id,
            status=TenantExposurePolicyStatus.ACTIVE.value,
        ).count(),
        'advanced_intent_count': active_advanced,
        'blockers': blockers,
        'executable': not blockers,
    }


def request_tenant_decommission_committed(
    *,
    tenant_id: str,
    actor: User | None = None,
) -> dict[str, Any]:
    preflight = build_tenant_decommission_preflight(tenant_id)
    tenant = preflight['tenant']
    blockers = list(preflight['blockers'])
    if blockers:
        raise TenantDecommissionBlocked(' '.join(blockers))

    retry = tenant.lifecycle_status == TenantLifecycleStatus.DECOMMISSIONING.value
    tenant.lifecycle_status = TenantLifecycleStatus.DECOMMISSIONING.value
    evidence = dict(tenant.provider_evidence_json or {})
    evidence['decommission'] = {
        'phase': 'requested',
        'requested_at': _now().isoformat(),
        'provider_key': tenant.provider_key,
        'reconciliation_authority': tenant.reconciliation_authority,
        'tenant_generation': tenant.generation,
        'retry': retry,
        'secret_material_persisted': False,
    }
    tenant.provider_evidence_json = evidence
    _record_event(
        tenant=tenant,
        actor=actor,
        action='tenant.decommission_retried' if retry else 'tenant.decommission_requested',
        summary='Tenant governed decommission was requested and new mutations are frozen.',
        outcome='queued',
        stage='freeze',
    )
    db.session.commit()
    return {key: value for key, value in preflight.items() if key != 'tenant'}


def _progress(callback: ProgressCallback | None, percent: int, message: str) -> None:
    if callback is not None:
        callback(percent, message)


def _actor(actor_user_id: int | None) -> User | None:
    if actor_user_id is None:
        return None
    return db.session.get(User, actor_user_id)


def _remove_managed_resources(tenant: Tenant, *, actor: User | None) -> int:
    removed = 0
    managed_resources = TenantManagedResourceIntent.query.filter(
        TenantManagedResourceIntent.tenant_id == tenant.id,
        TenantManagedResourceIntent.status != TenantManagedResourceStatus.DISABLED.value,
    ).order_by(TenantManagedResourceIntent.id.asc()).all()
    for intent in managed_resources:
        remove_managed_resource_committed(intent_id=intent.id, actor=actor)
        removed += 1
    return removed


def _release_policy_state(tenant: Tenant, *, actor: User | None) -> dict[str, int]:
    reservations_revoked = 0
    exposure_disabled = 0

    reservations = TenantDomainReservation.query.filter_by(
        tenant_id=tenant.id,
        status=TenantDomainReservationStatus.ACTIVE.value,
    ).order_by(TenantDomainReservation.id.asc()).all()
    for reservation in reservations:
        reservation.status = TenantDomainReservationStatus.REVOKED.value
        reservations_revoked += 1

    policies = TenantExposurePolicy.query.filter_by(
        tenant_id=tenant.id,
        status=TenantExposurePolicyStatus.ACTIVE.value,
    ).order_by(TenantExposurePolicy.id.asc()).all()
    for policy in policies:
        policy.status = TenantExposurePolicyStatus.DISABLED.value
        exposure_disabled += 1

    if reservations_revoked or exposure_disabled:
        _record_event(
            tenant=tenant,
            actor=actor,
            action='tenant.decommission_policy_released',
            summary='Tenant domain reservations and exposure policy state were retired for decommission.',
            outcome='success',
            stage='policy_cleanup',
            detail=(
                f'{reservations_revoked} domain reservations revoked; '
                f'{exposure_disabled} exposure policies disabled.'
            ),
        )
        db.session.commit()

    return {
        'domain_reservations_revoked': reservations_revoked,
        'exposure_policies_disabled': exposure_disabled,
    }

def _verify_terminal_state(tenant: Tenant) -> None:
    blockers: list[str] = []
    credential_count = _active_credential_count(tenant.id)
    grant_count = _active_grant_count(tenant.id)
    membership_count = _active_membership_count(tenant.id)
    namespace_count = (
        TenantNamespace.query.join(
            TenantEnvironment,
            TenantNamespace.tenant_environment_id == TenantEnvironment.id,
        )
        .filter(
            TenantEnvironment.tenant_id == tenant.id,
            TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        )
        .count()
    )
    if credential_count:
        blockers.append(f'{credential_count} credentials remain active')
    if grant_count:
        blockers.append(f'{grant_count} Access Grants remain active')
    if membership_count:
        blockers.append(f'{membership_count} memberships remain active')
    if namespace_count:
        blockers.append(f'{namespace_count} namespaces are not provider-verified absent')
    if blockers:
        raise TenantDecommissionBlocked('Final teardown verification failed: ' + '; '.join(blockers) + '.')


def execute_tenant_decommission(
    *,
    tenant_id: str,
    actor_user_id: int | None,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Execute idempotent provider-aware Tenant teardown while preserving audit history."""

    actor = _actor(actor_user_id)
    stage = 'preflight'
    try:
        preflight = build_tenant_decommission_preflight(tenant_id)
        tenant = preflight['tenant']
        if tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONING.value:
            raise TenantDecommissionBlocked('Tenant must be frozen in Decommissioning state before worker execution.')
        if preflight['blockers']:
            raise TenantDecommissionBlocked(' '.join(preflight['blockers']))

        _progress(progress, 5, 'Tenant frozen; validating provider authority.')

        stage = 'credentials'
        credentials = TenantCredential.query.filter(
            TenantCredential.tenant_id == tenant.id,
            TenantCredential.status != TenantCredentialStatus.REVOKED.value,
        ).order_by(TenantCredential.id.asc()).all()
        for credential in credentials:
            revoke_credential_committed(credential_id=credential.id, actor=actor)
        _progress(progress, 20, 'Credentials revoked and provider access removed.')

        stage = 'access_grants'
        grants = TenantAccessGrant.query.filter_by(
            tenant_id=tenant.id,
            status=TenantAccessGrantStatus.ACTIVE.value,
        ).order_by(TenantAccessGrant.id.asc()).all()
        for grant in grants:
            revoke_access_grant_committed(grant_id=grant.id, actor=actor)
        _progress(progress, 35, 'Access Grants revoked and Kubernetes RBAC cleanup verified.')

        stage = 'memberships'
        memberships = TenantMembership.query.filter_by(
            tenant_id=tenant.id,
            status=TenantMembershipStatus.ACTIVE.value,
        ).order_by(TenantMembership.id.asc()).all()
        for membership in memberships:
            revoke_membership_committed(membership_id=membership.id, actor=actor)
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None:
            raise TenantDecommissionBlocked('Tenant disappeared during governed teardown.')
        retired_groups = 0
        for group in tenant.groups:
            if group.enabled:
                group.enabled = False
                retired_groups += 1
        if retired_groups:
            _record_event(
                tenant=tenant,
                actor=actor,
                action='tenant.decommission_groups_retired',
                summary='Tenant Groups were disabled after dependent memberships were revoked.',
                outcome='success',
                stage='memberships',
                detail=f'{retired_groups} Tenant Groups disabled.',
            )
        db.session.commit()
        _progress(progress, 48, 'Memberships retired and Tenant Groups disabled.')

        stage = 'managed_resources'
        managed_resources_removed = _remove_managed_resources(tenant, actor=actor)
        _progress(progress, 56, 'Tenant-managed provider resources were removed before namespace teardown.')

        stage = 'namespaces'
        namespaces = (
            TenantNamespace.query.join(
                TenantEnvironment,
                TenantNamespace.tenant_environment_id == TenantEnvironment.id,
            )
            .filter(TenantEnvironment.tenant_id == tenant.id)
            .order_by(TenantNamespace.id.asc())
            .all()
        )
        deprovisioned_namespaces: list[str] = []
        for namespace in namespaces:
            if namespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value:
                deprovision_native_namespace_committed(namespace_id=namespace.id)
            deprovisioned_namespaces.append(namespace.namespace)
        _progress(progress, 82, 'Kubernetes confirmed managed namespaces are absent.')

        stage = 'policy_cleanup'
        release_counts = _release_policy_state(tenant, actor=actor)
        _progress(progress, 90, 'Tenant-owned reservation and exposure state retired.')

        stage = 'provider_verification'
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None:
            raise TenantDecommissionBlocked('Tenant disappeared before final provider verification.')
        provider_cleanup: dict[str, object]
        if (
            tenant.provider_key == 'native_kubernetes'
            and tenant.provider_state == 'native'
            and tenant.reconciliation_authority == 'native_kubernetes'
        ):
            provider_cleanup = {
                'provider': 'native_kubernetes',
                'provider_verified_absent': True,
                'tenant_object_required': False,
                'secret_material_persisted': False,
            }
        elif (
            tenant.provider_key == 'capsule'
            and tenant.provider_state == 'capsule'
            and tenant.reconciliation_authority == 'capsule'
        ):
            cluster = db.session.get(Cluster, tenant.cluster_id)
            if cluster is None:
                raise TenantDecommissionBlocked('Tenant cluster disappeared before Capsule provider verification.')
            provider_evidence = dict(tenant.provider_evidence_json or {})
            provider_cleanup = delete_capsule_tenant_verified(
                cluster=cluster,
                api_version=str(provider_evidence.get('provider_api_version') or '').strip(),
                tenant_name=str(provider_evidence.get('provider_reference') or tenant.provider_reference or '').strip(),
                kaori_tenant_id=tenant.id,
                generation=int(tenant.generation or 1),
                expected_uid=str(provider_evidence.get('provider_uid') or '').strip() or None,
            )
        else:
            raise TenantDecommissionBlocked('Provider authority changed during teardown; final state fails closed.')
        _verify_terminal_state(tenant)

        stage = 'finalize'
        tenant.lifecycle_status = TenantLifecycleStatus.DECOMMISSIONED.value
        evidence = dict(tenant.provider_evidence_json or {})
        evidence['decommission'] = {
            'phase': 'completed',
            'completed_at': _now().isoformat(),
            'provider_key': tenant.provider_key,
            'reconciliation_authority': tenant.reconciliation_authority,
            'provider_verified_absent': True,
            'provider_cleanup': provider_cleanup,
            'namespaces': deprovisioned_namespaces,
            'tenant_generation': tenant.generation,
            'secret_material_persisted': False,
        }
        tenant.provider_evidence_json = evidence
        _record_event(
            tenant=tenant,
            actor=actor,
            action='tenant.decommission_completed',
            summary='Tenant governed teardown completed after provider absence verification.',
            outcome='success',
            stage=stage,
            detail=f'{len(deprovisioned_namespaces)} namespaces verified absent.',
        )
        db.session.commit()
        _progress(progress, 100, 'Tenant decommission completed with committed provider evidence.')
        return {
            'tenant_id': tenant.id,
            'tenant_name': tenant.name,
            'tenant_slug': tenant.slug,
            'tenant_generation': tenant.generation,
            'cluster_id': tenant.cluster_id,
            'provider_key': tenant.provider_key,
            'lifecycle_status': tenant.lifecycle_status,
            'namespaces_deprovisioned': deprovisioned_namespaces,
            'managed_resources_removed': managed_resources_removed,
            'provider_cleanup': provider_cleanup,
            **release_counts,
        }
    except Exception as exc:
        db.session.rollback()
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is not None and tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value:
            tenant.lifecycle_status = TenantLifecycleStatus.DECOMMISSIONING.value
            evidence = dict(tenant.provider_evidence_json or {})
            evidence['decommission'] = {
                **dict(evidence.get('decommission') or {}),
                'phase': 'blocked',
                'blocked_at': _now().isoformat(),
                'blocked_stage': stage,
                'message': str(exc)[:1000],
                'provider_key': tenant.provider_key,
                'reconciliation_authority': tenant.reconciliation_authority,
                'secret_material_persisted': False,
            }
            tenant.provider_evidence_json = evidence
            _record_event(
                tenant=tenant,
                actor=actor,
                action='tenant.decommission_blocked',
                summary='Tenant decommission stopped fail-closed and requires operator remediation.',
                outcome='failed',
                stage=stage,
                detail=str(exc)[:1000],
            )
            db.session.commit()
        raise
