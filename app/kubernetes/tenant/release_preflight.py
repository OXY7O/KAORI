from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.decommission_service import (
    _active_credential_count,
    _active_grant_count,
    _active_membership_count,
)
from app.kubernetes.tenant.external_access_observation import latest_external_capsule_access_evidence
from app.models import AuditEvent, Cluster
from app.models.tenant import Tenant, TenantEnvironment, TenantNamespace
from app.models.tenant_advanced import TenantAdvancedCapabilityIntent, TenantAdvancedCapabilityStatus
from app.models.tenant_managed_resource import TenantManagedResourceIntent, TenantManagedResourceStatus
from app.models.tenant_policy import (
    TenantDomainReservation,
    TenantDomainReservationStatus,
    TenantExposurePolicy,
    TenantExposurePolicyStatus,
)

_TARGET = 'kubernetes_tenant_release_preflight'


def _release_blockers(tenant: Tenant, namespace_rows: list[TenantNamespace], *, counts: dict[str, int]) -> list[str]:
    blockers: list[str] = []
    if tenant.ownership_status != 'adopted':
        blockers.append('Release Governance is only applicable to externally adopted Tenants.')
    if tenant.lifecycle_status != 'ready':
        blockers.append('Tenant must be Ready before a provider-preserving release.')
    if tenant.provider_state not in {'native', 'capsule'}:
        blockers.append('Degraded provider authority cannot be released without recovery.')
    if tenant.provider_key == 'capsule' and tenant.reconciliation_authority != 'capsule':
        blockers.append('Capsule reconciliation authority is inconsistent.')
    if tenant.provider_key == 'native_kubernetes' and tenant.reconciliation_authority != 'native_kubernetes':
        blockers.append('Native reconciliation authority is inconsistent.')

    for kind, amount in counts.items():
        if amount:
            blockers.append(f'{amount} active {kind} must be governed/handoff-reviewed before release.')
    for record in namespace_rows:
        if record.ownership_status != 'adopted' and record.provisioning_status != 'deprovisioned':
            blockers.append(f'{record.namespace} is KAORI-created/managed, not safely releasable.')
        if record.resource_profile_id is not None:
            blockers.append(f'{record.namespace} has KAORI-managed allocation; explicit provider handoff is required.')
    return blockers


def latest_tenant_release_preflight(tenant_id: str) -> dict[str, Any] | None:
    row = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc()).first()
    )
    return dict(row.metadata_json or {}) if row else None


def review_tenant_release_preflight_committed(*, tenant_id: str, actor_user_id: int) -> dict[str, Any]:
    """Explicit, read-only provider identity proof; NEVER release or decommission."""
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError('Selected Tenant is unavailable.')
    rows = (
        TenantNamespace.query.join(TenantEnvironment, TenantNamespace.tenant_environment_id == TenantEnvironment.id)
        .filter(TenantEnvironment.tenant_id == tenant_id)
        .order_by(TenantNamespace.id.asc())
        .all()
    )
    counts = {
        'credentials': _active_credential_count(tenant_id),
        'Access Grants': _active_grant_count(tenant_id),
        'Memberships': _active_membership_count(tenant_id),
        'managed resources': TenantManagedResourceIntent.query.filter(
            TenantManagedResourceIntent.tenant_id == tenant_id,
            TenantManagedResourceIntent.status != TenantManagedResourceStatus.DISABLED.value,
        ).count(),
        'advanced capabilities': TenantAdvancedCapabilityIntent.query.filter(
            TenantAdvancedCapabilityIntent.tenant_id == tenant_id,
            TenantAdvancedCapabilityIntent.status != TenantAdvancedCapabilityStatus.DISABLED.value,
        ).count(),
        'domain reservations': TenantDomainReservation.query.filter_by(
            tenant_id=tenant_id, status=TenantDomainReservationStatus.ACTIVE.value
        ).count(),
        'exposure policies': TenantExposurePolicy.query.filter_by(
            tenant_id=tenant_id, status=TenantExposurePolicyStatus.ACTIVE.value
        ).count(),
    }
    blockers = _release_blockers(tenant, rows, counts=counts)
    provider: list[dict[str, str]] = []
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        blockers.append('Kubernetes cluster is not available for live handoff verification.')
    elif tenant.provider_state in {'capsule', 'native'}:
        client = runtime_adapter.build_client(cluster)
        if tenant.provider_key == 'capsule':
            try:
                obj = client.custom_objects_api().get_cluster_custom_object(
                    'capsule.clastix.io', 'v1beta2', 'tenants',
                    str(tenant.provider_reference or ''), _request_timeout=5,
                )
                metadata = obj.get('metadata') or {}
                uid = str(metadata.get('uid') or '')
                reference = str((tenant.provider_evidence_json or {}).get('provider_uid') or '')
                if not uid or not metadata.get('resourceVersion') or (reference and uid != reference):
                    blockers.append('Capsule Tenant provider UID/resourceVersion changed or is missing.')
                else:
                    provider.append({
                        'kind': 'CapsuleTenant', 'name': str(tenant.provider_reference),
                        'uid': uid, 'resource_version': str(metadata['resourceVersion']),
                    })
            except (ApiException, ValueError, AttributeError):
                blockers.append('Capsule Tenant live read failed; release remains blocked.')
            external = latest_external_capsule_access_evidence(tenant_id)
            if not external:
                blockers.append('Inspect external Capsule owners and RBAC before Release Governance.')
            elif (
                external.get('provider_uid') != (provider[0]['uid'] if provider else None)
                or external.get('resource_version')
                != (provider[0]['resource_version'] if provider else None)
            ):
                blockers.append('External Capsule access observation is stale or does not match current Tenant.')
            else:
                try:
                    observed_at = datetime.fromisoformat(str(external.get('observed_at') or ''))
                except ValueError:
                    observed_at = None
                age_seconds = (
                    (datetime.now(UTC) - observed_at).total_seconds()
                    if observed_at and observed_at.tzinfo else -1
                )
                if age_seconds < 0 or age_seconds > 3600:
                    blockers.append('External Capsule ownership evidence must be inspected again.')
        elif tenant.provider_key == 'native_kubernetes':
            for record in rows:
                if record.provisioning_status == 'deprovisioned':
                    continue
                try:
                    obj = client.core_api().read_namespace(record.namespace, _request_timeout=5)
                except ApiException:
                    blockers.append(f'{record.namespace} could not be read live for handoff.')
                    continue
                metadata = getattr(obj, 'metadata', None)
                uid = str(getattr(metadata, 'uid', None) or '')
                version = str(getattr(metadata, 'resource_version', None) or '')
                if not uid or not version or (record.provider_reference and uid != record.provider_reference):
                    blockers.append(f'{record.namespace} Namespace UID/resourceVersion mismatch.')
                else:
                    provider.append({
                        'kind': 'Namespace', 'name': record.namespace,
                        'uid': uid, 'resource_version': version,
                    })

    evidence = {
        'tenant_id': tenant.id,
        'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'ownership': tenant.ownership_status,
        'provider': tenant.provider_key,
        'status': 'blocked' if blockers else 'handoff_review_required',
        'blockers': blockers,
        'dependency_counts': counts,
        'live_provider_identity': provider,
        'checked_at': datetime.now(UTC).isoformat(),
        'provider_resource_deleted': False,
        'provider_rbac_modified': False,
        'release_executed': False,
        'release_execution_available': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type=_TARGET, target_id=tenant.id,
        action='tenant.release.preflight_observed',
        summary='Reviewed provider-preserving Tenant release readiness; no governance state changed.',
        metadata_json=evidence,
    ))
    db.session.commit()
    return evidence
