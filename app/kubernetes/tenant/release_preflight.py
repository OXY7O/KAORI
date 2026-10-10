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
from app.kubernetes.tenant.allocation_observation import observe_native_namespace_allocation
from app.kubernetes.tenant.capsule_allocation_observation import _capsule_status_namespace_names
from app.kubernetes.tenant.external_access_observation import latest_external_capsule_access_evidence
from app.kubernetes.tenant.release_handoff_inventory import (
    capsule_tenant_handoff_evidence,
    capsule_namespace_handoff_evidence,
    handoff_fingerprint,
    native_namespace_handoff_evidence,
)
from app.models import AuditEvent, Cluster
from app.models.tenant import (
    Tenant, TenantEnvironment, TenantGroup, TenantLifecycleStatus, TenantNamespace,
    TenantNamespaceProvisioningStatus,
)
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

    provider_evidence = getattr(tenant, 'provider_evidence_json', None) or {}
    if provider_evidence.get('provider_mutation_performed') is not False:
        blockers.append(
            'Adoption performed KAORI-owned provider mutations. Complete independently verified '
            'allocation/policy handoff before Release; database-only abandonment is prohibited.'
        )
    for kind, amount in counts.items():
        if amount:
            blockers.append(f'{amount} active {kind} must be governed/handoff-reviewed before release.')
    for record in namespace_rows:
        record_evidence = getattr(record, 'provisioning_evidence_json', None) or {}
        if record_evidence.get('provider_mutation_performed') is True:
            blockers.append(
                f'{record.namespace} has KAORI-mutated Namespace provider controls; '
                'independently approved external handoff is required.'
            )
        elif record_evidence.get('provider_mutation_performed') is not False:
            blockers.append(
                f'{record.namespace} has missing or unverified provider mutation provenance; '
                'investigate before approving handoff.'
            )
        if record.provisioning_status != TenantNamespaceProvisioningStatus.READY.value:
            blockers.append(f'{record.namespace} is not Ready for provider-preserving release.')
        if record.ownership_status != 'adopted' and record.provisioning_status != 'deprovisioned':
            blockers.append(f'{record.namespace} is KAORI-created/managed, not safely releasable.')
        if record.resource_profile_id is not None:
            blockers.append(
                f'{record.namespace} has a KAORI-managed allocation linked to a Resource Profile. '
                'Before Release, its Namespace allocation controls must be handed over explicitly '
                'with independent approval and authoritative provider read-back. '
                'KAORI cannot silently abandon the committed allocation or delete provider resources.'
            )
    return blockers


def _release_dependency_counts(tenant_id: str) -> dict[str, int]:
    """Single dependency authority shared by preflight and guarded Release."""
    return {
        'credentials': _active_credential_count(tenant_id),
        'Access Grants': _active_grant_count(tenant_id),
        'Memberships': _active_membership_count(tenant_id),
        'enabled Groups': TenantGroup.query.filter_by(tenant_id=tenant_id, enabled=True).count(),
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
    counts = _release_dependency_counts(tenant_id)
    blockers = _release_blockers(tenant, rows, counts=counts)
    provider: list[dict[str, str]] = []
    handoff_components: list[dict[str, str]] = []
    if len(rows) > 30:
        blockers.append('Release handoff inventory exceeds 30 namespaces; review scope before Release.')
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
                    items, handoff_blockers = capsule_tenant_handoff_evidence(
                        tenant=tenant, tenant_item=obj
                    )
                    handoff_components.extend(items)
                    blockers.extend(handoff_blockers)
                    status_names = _capsule_status_namespace_names(obj)
                    for record in rows[:30]:
                        if record.provisioning_status in {'deprovisioned', 'released'}:
                            continue
                        try:
                            namespace = client.core_api().read_namespace(
                                record.namespace, _request_timeout=5
                            )
                            component, issues = capsule_namespace_handoff_evidence(
                                record=record, namespace=namespace,
                                tenant_name=str(tenant.provider_reference),
                                tenant_id=tenant.id,
                                status_namespace_names=status_names,
                            )
                            handoff_components.append({
                                **component, 'namespace': record.namespace
                            })
                            blockers.extend(issues)
                            provider.append({
                                'kind': 'Namespace',
                                'name': record.namespace,
                                'uid': component['uid'],
                                'resource_version': component['resource_version'],
                            })
                        except (ApiException, ValueError, TypeError, AttributeError):
                            blockers.append(
                                f'Capsule Namespace/{record.namespace} identity or ownership '
                                'could not be verified for Release.'
                            )
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
            for record in rows[:30]:
                if record.provisioning_status in {'deprovisioned', 'released'}:
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
                    try:
                        observation = observe_native_namespace_allocation(
                            client.core_api(), record.namespace
                        )
                        items, handoff_blockers = native_namespace_handoff_evidence(
                            record=record, namespace=obj, observation=observation,
                            tenant_id=tenant.id,
                        )
                        handoff_components.extend([
                            {**component, 'namespace': record.namespace}
                            for component in items
                        ])
                        blockers.extend(handoff_blockers)
                    except (ApiException, ValueError, TypeError, AttributeError):
                        blockers.append(
                            f'{record.namespace} allocation handoff inventory could not be read.'
                        )

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
        'handoff_components': handoff_components,
        'handoff_fingerprint': handoff_fingerprint(handoff_components),
        'handoff_required_count': sum(
            item['handoff'] != 'observe_only' for item in handoff_components
        ),
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


def release_adopted_tenant_committed(
    *, tenant_id: str, actor_user_id: int, approved: bool
) -> dict[str, Any]:
    """Release *only* observation-only adopted generations with verified safe handoff.

    Existing active external resources stay untouched. This intentionally blocks
    KAORI-modified provider resources until a separate approved handoff workflow
    can prove their ownership transfer. No Kubernetes mutation is performed.
    """
    if not approved:
        raise ValueError('Explicit provider-preserving Release approval is required.')
    previous = latest_tenant_release_preflight(tenant_id)
    if previous is None or previous.get('status') != 'handoff_review_required':
        raise ValueError('Run an eligible Release preflight before execution.')
    try:
        checked_at = datetime.fromisoformat(str(previous.get('checked_at') or ''))
    except ValueError as exc:
        raise ValueError('Release preflight timestamp is missing or invalid.') from exc
    age = (datetime.now(UTC) - checked_at).total_seconds() if checked_at.tzinfo else -1
    if age < 0 or age > 900:
        raise ValueError('Release preflight is stale; review it again before releasing.')

    # Read the authoritative Kubernetes objects *again* and commit a fresh
    # preflight before mutating any KAORI-owned governance record.
    latest = review_tenant_release_preflight_committed(
        tenant_id=tenant_id, actor_user_id=actor_user_id
    )
    if latest['status'] != 'handoff_review_required' or latest['blockers']:
        raise ValueError('Release is blocked by newly observed provider or governance dependencies.')
    identity_keys = ('tenant_id', 'cluster_id', 'generation', 'provider', 'ownership')
    if any(previous.get(key) != latest.get(key) for key in identity_keys):
        raise ValueError('Tenant authority changed since approved Release preflight.')
    old_objects = sorted(
        (row['kind'], row['name'], row['uid'], row['resource_version'])
        for row in previous.get('live_provider_identity') or []
    )
    new_objects = sorted(
        (row['kind'], row['name'], row['uid'], row['resource_version'])
        for row in latest.get('live_provider_identity') or []
    )
    if not old_objects or new_objects != old_objects:
        raise ValueError('Provider UID/resourceVersion changed; repeat Release preflight.')
    if (
        not previous.get('handoff_components')
        or previous.get('handoff_fingerprint') != latest.get('handoff_fingerprint')
    ):
        raise ValueError('Provider allocation or ownership handoff evidence changed; repeat preflight.')

    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value:
        raise ValueError('Tenant lifecycle changed during Release approval.')
    records = (
        TenantNamespace.query.join(
            TenantEnvironment, TenantNamespace.tenant_environment_id == TenantEnvironment.id
        ).filter(TenantEnvironment.tenant_id == tenant_id)
        .order_by(TenantNamespace.id.asc()).with_for_update().all()
    )
    if tenant.ownership_status != 'adopted':
        raise ValueError('Only adopted Tenant authority can be released.')
    if any(
        row.provisioning_status != TenantNamespaceProvisioningStatus.READY.value
        or row.resource_profile_id is not None or row.ownership_status != 'adopted'
        for row in records
    ):
        raise ValueError('A Namespace has active KAORI allocation or an unsafe lifecycle.')
    if _release_blockers(tenant, records, counts=_release_dependency_counts(tenant_id)):
        raise ValueError('Tenant dependencies changed after preflight; Release remains blocked.')
    provider_evidence = dict(tenant.provider_evidence_json or {})
    if provider_evidence.get('provider_mutation_performed') is not False:
        raise ValueError('KAORI-owned provider controls remain; Release requires independent handoff proof.')

    now = datetime.now(UTC)
    result = {
        'tenant_id': tenant.id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation, 'provider': tenant.provider_key,
        'status': 'released', 'released_at': now.isoformat(),
        'provider_identity': new_objects,
        'preflight_checked_at': latest['checked_at'],
        'provider_resource_deleted': False,
        'provider_mutation_performed': False,
        'rbac_mutation_performed': False,
        'secret_material_persisted': False,
        'released_namespace_count': len(records),
    }
    for record in records:
        prior_evidence = dict(record.provisioning_evidence_json or {})
        prior_evidence['release_governance'] = {
            'status': 'released', 'released_at': now.isoformat(),
            'tenant_id': tenant.id, 'generation': record.generation,
            'provider_uid': record.provider_reference,
            'provider_preserved': True, 'provider_mutation_performed': False,
        }
        record.provisioning_evidence_json = prior_evidence
        record.provisioning_status = TenantNamespaceProvisioningStatus.RELEASED.value
        record.provisioning_message = 'Governance Released; provider Namespace preserved for external management.'
    provider_evidence['release_governance'] = result
    tenant.provider_evidence_json = provider_evidence
    tenant.lifecycle_status = TenantLifecycleStatus.RELEASED.value
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type='kubernetes_tenant_release',
        target_id=tenant.id, action='tenant.release.governance_released',
        summary='Released observed Tenant governance; verified provider objects remained unchanged.',
        metadata_json=result,
    ))
    db.session.commit()
    return result


def release_verified_native_tenant_committed(
    *, tenant_id: str, actor_user_id: int, plan_sha256: str, approved: bool,
) -> dict[str, Any]:
    """Finalize only fully verified #1048 Native handoff, preserving provider objects.

    Reuses canonical Tenant/Namespace Released statuses and audit lineage.
    An accepted external owner transfer is distinct from decommission.
    """
    if not approved:
        raise ValueError('Explicit provider-preserving Native Release confirmation is required.')
    from app.kubernetes.tenant.native_platform_admin_authority import require_platform_admin_actor
    require_platform_admin_actor(actor_user_id)
    # Delayed imports avoid a cycle: the executor uses canonical preflight
    # dependency and provider evidence helpers from this module.
    from app.kubernetes.tenant.native_handoff_dry_run import _read_resource
    from app.kubernetes.tenant.native_handoff_readback import (
        _latest_native_dry_run, verify_external_native_component,
    )
    from app.kubernetes.tenant.native_handoff_executor import latest_native_handoff_execution
    from app.kubernetes.tenant.native_successor_acceptance import latest_native_successor_acceptance
    from app.kubernetes.tenant.release_handoff_approval import (
        _plan_hash, latest_release_handoff_approval, latest_release_handoff_plan,
    )

    plan = latest_release_handoff_plan(tenant_id)
    approval = latest_release_handoff_approval(tenant_id)
    acceptance = latest_native_successor_acceptance(tenant_id)
    execution = latest_native_handoff_execution(tenant_id)
    preview = _latest_native_dry_run(tenant_id)
    if (
        not plan or not approval or not acceptance or not execution or not preview
        or plan.get('tenant_id') != tenant_id
        or plan.get('plan_sha256') != plan_sha256 or _plan_hash(plan) != plan_sha256
        or plan.get('provider') != 'native_kubernetes'
        or approval.get('plan_sha256') != plan_sha256
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('approved_by') == plan.get('requested_by')
        or acceptance.get('status') != 'platform_admin_handoff_accepted'
        or acceptance.get('authority_mode') != 'platform_admin_governed'
        or acceptance.get('plan_sha256') != plan_sha256
        or acceptance.get('consent_verified') is not True
        or acceptance.get('resource_authority_verified') is not True
        or acceptance.get('verified_provider_identity') is not True
        or acceptance.get('provider_username') != execution.get('provider_username')
        or acceptance.get('provider_credential_id') != execution.get('provider_credential_id')
        or execution.get('authority_mode') != 'platform_admin_governed'
        or execution.get('provider_authority_verified') is not True
        or execution.get('status') != 'provider_handoff_verified'
        or execution.get('plan_sha256') != plan_sha256
        or execution.get('provider_handoff_verified') is not True
        or execution.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or preview.get('status') != 'dry_run_passed'
        or preview.get('plan_sha256') != plan_sha256
        or preview.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
    ):
        raise ValueError('Fully verified Native successor consent and provider handoff are required.')
    expected = preview.get('previewed_components')
    transferred = execution.get('verified_components')
    if (
        not isinstance(expected, list) or not 0 < len(expected) <= 100
        or not isinstance(transferred, list) or len(transferred) != len(expected)
        or execution.get('expected_component_count') != len(expected)
        or execution.get('verified_count') != len(expected)
        or len({(x.get('namespace'), x.get('kind'), x.get('name'), x.get('uid')) for x in expected})
        != len(expected)
    ):
        raise ValueError('Native provider handoff coverage is incomplete or ambiguous.')
    tenant = Tenant.query.filter_by(id=tenant_id).with_for_update().one_or_none()
    if (
        tenant is None or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.ownership_status != 'adopted'
        or tenant.cluster_id != plan.get('cluster_id')
        or tenant.generation != plan.get('generation')
    ):
        raise ValueError('Canonical Native Tenant authority changed before Release.')
    rows = (
        TenantNamespace.query.join(
            TenantEnvironment, TenantNamespace.tenant_environment_id == TenantEnvironment.id
        ).filter(TenantEnvironment.tenant_id == tenant_id)
        .order_by(TenantNamespace.id.asc()).with_for_update().all()
    )
    if not rows or any(
        row.provisioning_status != TenantNamespaceProvisioningStatus.READY.value
        or row.ownership_status != 'adopted'
        for row in rows
    ):
        raise ValueError('A Native Namespace is not an adopted Ready resource.')
    counts = _release_dependency_counts(tenant_id)
    if any(type(value) is not int or value != 0 for value in counts.values()):
        raise ValueError('Active Tenant grants, credentials or dependencies prevent Release.')
    current_plan = latest_release_handoff_plan(tenant_id)
    current_execution = latest_native_handoff_execution(tenant_id)
    if (
        not current_plan or current_plan.get('plan_sha256') != plan_sha256
        or not current_execution or current_execution.get('status') != 'provider_handoff_verified'
        or current_execution.get('plan_sha256') != plan_sha256
    ):
        raise ValueError('Concurrent provider handoff state changed before Release.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Canonical Native provider cluster is unavailable.')
    core = runtime_adapter.build_client(cluster).core_api()
    actual: list[dict[str, Any]] = []
    verified_ns: dict[str, dict[str, Any]] = {}
    for item in expected:
        live = _read_resource(core, item)
        outcome = verify_external_native_component(
            before=item, current=live,
            successor_owner=str(plan['successor_owner']),
        )
        actual.append({**outcome, 'namespace': item.get('namespace')})
        if item.get('kind') == 'Namespace':
            verified_ns[item['name']] = outcome
    if not verified_ns or len(verified_ns) != len(rows):
        raise ValueError('Native Namespace inventory does not cover all adopted Tenant namespaces.')
    for row in rows:
        namespace = verified_ns.get(row.namespace)
        if (
            not namespace or namespace['uid'] != row.provider_reference
            or row.cluster_id != tenant.cluster_id
        ):
            raise ValueError('Committed Namespace generation and provider UID differ from handoff.')
    expected_keys = {(x.get('namespace'), x.get('kind'), x.get('name'), x.get('uid')) for x in expected}
    actual_keys = {(x.get('namespace'), x.get('kind'), x.get('name'), x.get('uid')) for x in actual}
    if actual_keys != expected_keys:
        raise ValueError('Provider post-handoff read-back did not cover the exact approved scope.')

    now = datetime.now(UTC)
    result = {
        'status': 'released', 'release_mode': 'managed_handoff',
        'tenant_id': tenant.id, 'cluster_id': tenant.cluster_id,
        'generation': tenant.generation, 'provider': tenant.provider_key,
        'plan_sha256': plan_sha256, 'handoff_fingerprint': plan['handoff_fingerprint'],
        'successor_owner': plan['successor_owner'],
        'authority_mode': 'platform_admin_governed',
        'approved_by_platform_admin': acceptance['accepted_by'],
        'provider_username': acceptance['provider_username'],
        'provider_credential_id': acceptance['provider_credential_id'],
        'released_at': now.isoformat(),
        'released_namespace_count': len(rows),
        'verified_components': actual,
        'provider_handoff_verified': True,
        'successor_consent_verified': True,
        'provider_resource_deleted': False,
        'rbac_mutation_performed': False,
        'secret_material_persisted': False,
    }
    for row in rows:
        record_evidence = dict(row.provisioning_evidence_json or {})
        record_evidence['release_governance'] = {
            'status': 'released', 'release_mode': 'managed_handoff',
            'tenant_id': tenant.id, 'generation': row.generation,
            'provider_uid': row.provider_reference,
            'provider_resource_version': verified_ns[row.namespace]['resource_version'],
            'released_at': now.isoformat(),
            'plan_sha256': plan_sha256,
            'successor_owner': plan['successor_owner'],
            'provider_handoff_verified': True,
            'provider_preserved': True,
        }
        row.provisioning_evidence_json = record_evidence
        row.provisioning_status = TenantNamespaceProvisioningStatus.RELEASED.value
        row.provisioning_message = 'Governance Released after verified Native successor handoff; provider preserved.'
    prior = dict(tenant.provider_evidence_json or {})
    prior['release_governance'] = result
    tenant.provider_evidence_json = prior
    tenant.lifecycle_status = TenantLifecycleStatus.RELEASED.value
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id, target_type='kubernetes_tenant_release',
        target_id=tenant.id, action='tenant.release.native_verified_governance_released',
        summary='Verified Native handoff; KAORI governance Released with all provider resources preserved.',
        metadata_json=result,
    ))
    db.session.commit()
    return result
