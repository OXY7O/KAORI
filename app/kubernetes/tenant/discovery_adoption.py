from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_cutover import reconcile_adopted_native_allocation
from app.kubernetes.tenant.allocation_observation import observe_native_namespace_allocation
from app.kubernetes.tenant.capacity_governance import enforce_existing_namespace_allocation_preflight
from app.kubernetes.tenant.capsule_allocation_observation import (
    _capsule_status_namespace_names,
    observe_capsule_tenant_allocation,
)
from app.kubernetes.tenant.capsule_namespace_attachment_authority import (
    validate_capsule_namespace_attachment,
)
from app.kubernetes.tenant.capsule_tenant import qualify_capsule_tenant_adoption
from app.kubernetes.tenant.discovery_service import (
    _adoption_environment,
    _apply_capsule_allocation_capability_state,
    _capsule_phase,
    _managed_capsule_map,
    _managed_namespace_map,
    _materialize_capsule_namespace_policy_profile,
    _namespace_phase,
    _native_management,
    _next_namespace_generation,
    _next_tenant_generation,
    _read_capsule_tenant,
    _take_over_capsule_allocation,
    _unclaimed_provider_ownership_reason,
    select_capsule_namespace_attachment_candidate,
)
from app.kubernetes.tenant.native_provider import tenant_workspace_connection_available
from app.kubernetes.tenant.service import (
    _materialize_adopted_baseline_profile,
    normalize_tenant_slug,
)
from app.models import Cluster
from app.models.cluster import ClusterStatus
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantOwnershipStatus,
)


@dataclass(frozen=True, slots=True)
class _AdoptionContext:
    cluster: Cluster
    client: Any
    provider_key: str
    resource_name: str
    environment_name: str
    tenant: Tenant
    now: datetime
    expected_provider_uid: str = ''
    expected_provider_resource_version: str = ''


def validate_adoption_provider_identity(
    *,
    expected_uid: str,
    observed_uid: str,
    expected_resource_version: str,
    observed_resource_version: str,
) -> None:
    """Match the exact provider UID/resourceVersion reviewed in Adoption Preflight."""
    if not all((expected_uid, observed_uid, expected_resource_version, observed_resource_version)):
        raise ValueError('Adoption requires complete preflight and live provider UID/resourceVersion evidence.')
    if expected_uid != observed_uid:
        raise ValueError('Provider UID changed since Adoption Preflight; refresh Discovery.')
    if expected_resource_version != observed_resource_version:
        raise ValueError('Provider resourceVersion changed since Adoption Preflight; refresh Discovery.')


def _prepare_adoption(source: Mapping[str, Any]) -> _AdoptionContext:
    cluster_id = str(source.get('cluster_id') or '').strip()
    provider_key = str(source.get('provider_key') or '').strip().lower()
    resource_name = str(source.get('resource_name') or '').strip()
    tenant_name = str(source.get('tenant_name') or resource_name).strip()
    expected_provider_uid = str(source.get('provider_uid') or '').strip()
    expected_provider_resource_version = str(source.get('provider_resource_version') or '').strip()
    environment_name = _adoption_environment(str(source.get('environment') or ''))

    if provider_key not in {'native_kubernetes', 'capsule'}:
        raise ValueError('Unsupported Tenant discovery provider.')
    if not resource_name:
        raise ValueError('Select a discovered provider object.')
    if not expected_provider_uid or not expected_provider_resource_version:
        raise ValueError('Adoption requires provider UID/resourceVersion from explicit Discovery preflight.')
    if not tenant_name or len(tenant_name) > 120:
        raise ValueError('Tenant name is required and must be at most 120 characters.')

    cluster = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(
            Cluster.id == cluster_id,
            Cluster.status == ClusterStatus.CONNECTED.value,
        )
        .first()
    )
    if cluster is None or not tenant_workspace_connection_available(cluster.kubernetes_connection):
        raise ValueError('The selected Kubernetes cluster is not available for Tenant adoption.')

    slug = normalize_tenant_slug(str(source.get('tenant_slug') or tenant_name))
    tenant = Tenant()
    tenant.cluster_id = cluster.id
    tenant.name = tenant_name
    tenant.slug = slug
    tenant.generation = _next_tenant_generation(cluster_id=str(cluster.id), slug=slug)
    tenant.description = f'Adopted from live {provider_key.replace("_", " ")} discovery.'
    tenant.lifecycle_status = TenantLifecycleStatus.READY.value
    tenant.ownership_status = TenantOwnershipStatus.ADOPTED.value
    return _AdoptionContext(
        cluster=cluster,
        client=runtime_adapter.build_client(cluster),
        provider_key=provider_key,
        resource_name=resource_name,
        environment_name=environment_name,
        tenant=tenant,
        now=datetime.now(UTC),
        expected_provider_uid=expected_provider_uid,
        expected_provider_resource_version=expected_provider_resource_version,
    )


def _require_re_adoption_handback_for_managed_release(
    *, provider_evidence: Mapping[str, Any], release_evidence: Mapping[str, Any],
    provider_uid: str | None = None, resource_version: str | None = None,
    namespace: str | None = None,
) -> None:
    """Require exact original Handback, or verified append-only residue RV lineage.

    An old successful Handback receipt is immutable. A newer metadata-only
    correction may legitimately advance the provider resourceVersion; it is
    accepted ONLY when a complete, committed verified recovery AuditEvent
    agrees with both the historical release and new Namespace generation.
    """
    if (
        provider_evidence.get('provider_mutation_performed') is False
        and release_evidence.get('release_mode') != 'managed_handoff'
        and release_evidence.get('provider_handoff_verified') is not True
    ):
        return
    handback = provider_evidence.get('handback_governance') or {}
    versions = handback.get('provider_resource_versions') or {}
    handback_rv = (
        versions.get(namespace) if namespace else handback.get('resource_version')
    )
    if (
        handback.get('status') != 'verified'
        or handback.get('release_plan_sha256') != release_evidence.get('plan_sha256')
        or handback.get('successor_owner') != release_evidence.get('successor_owner')
        or not provider_uid or handback.get('provider_uid') != provider_uid
        or not resource_version
    ):
        raise ValueError(
            'Previously managed Released resources require verified successor '
            'handback before a new KAORI Adoption generation.'
        )
    if handback_rv == resource_version:
        return

    recovery = provider_evidence.get('residual_recovery_governance') or {}
    recovery_versions = recovery.get('provider_resource_versions') or {}
    recovered_rv = (
        recovery_versions.get(namespace) if namespace else recovery.get('resource_version')
    )
    # The database projection is not independently sufficient. Require the
    # append-only terminal AuditEvent, its exact checksum and completed scope.
    from app.kubernetes.tenant.native_handoff_dry_run import _stable_sha256
    from app.kubernetes.tenant.native_residual_recovery_governance import (
        latest_native_residual_cleanup_execution,
    )

    tenant_id = release_evidence.get('tenant_id')
    receipt = (
        latest_native_residual_cleanup_execution(tenant_id)
        if isinstance(tenant_id, str) and tenant_id else None
    )
    if (
        not isinstance(recovery, Mapping)
        or recovery.get('status') != 'verified'
        or recovery.get('provider_metadata_only_verified') is not True
        or recovery.get('release_plan_sha256') != release_evidence.get('plan_sha256')
        or recovery.get('successor_owner', release_evidence.get('successor_owner'))
        != release_evidence.get('successor_owner')
        or not recovery.get('handback_plan_sha256')
        or recovery.get('provider_uid') != provider_uid
        or recovered_rv != resource_version
        or not isinstance(receipt, Mapping)
        or receipt.get('status') != 'verified'
        or receipt.get('tenant_id') != tenant_id
        or receipt.get('release_plan_sha256') != release_evidence.get('plan_sha256')
        or receipt.get('handback_plan_sha256') != recovery.get('handback_plan_sha256')
        or receipt.get('successor_owner') != release_evidence.get('successor_owner')
        or receipt.get('provider_specs_preserved') is not True
        or receipt.get('errors') != []
        or not isinstance(receipt.get('verified_components'), list)
        or receipt.get('verified_count') != receipt.get('expected_component_count')
        or receipt.get('verified_count') != len(receipt['verified_components'])
        or receipt.get('re_adopt_admitted') is not False
        or receipt.get('provider_mutation_performed') is not True
        or not receipt.get('receipt_sha256')
        or receipt.get('receipt_sha256') != recovery.get('receipt_sha256')
        or _stable_sha256({k: v for k, v in receipt.items()
                           if k != 'receipt_sha256'}) != receipt['receipt_sha256']
    ):
        raise ValueError('Verified post-Handback recovery evidence and current provider RV differ.')

    covered = [
        item for item in receipt.get('verified_components', [])
        if isinstance(item, Mapping) and item.get('kind') == 'Namespace'
        and item.get('uid') == provider_uid
        and item.get('resource_version') == resource_version
        and (namespace is None or item.get('name') == namespace)
    ]
    if len(covered) != 1:
        raise ValueError('Recovered Namespace identity is not unique in immutable provider evidence.')


def _released_predecessor_evidence(
    tenant: Tenant, *, provider_uid: str, resource_version: str | None = None,
) -> dict[str, Any] | None:
    """Correlate an adopted resource to exactly one prior Released generation."""
    previous = (
        Tenant.query.filter_by(cluster_id=tenant.cluster_id, slug=tenant.slug)
        .filter(Tenant.lifecycle_status == TenantLifecycleStatus.RELEASED.value)
        .order_by(Tenant.generation.desc()).first()
    )
    if previous is None:
        return None
    evidence = previous.provider_evidence_json or {}
    if previous.provider_key != tenant.provider_key:
        raise ValueError('Released Tenant provider differs; new adoption requires an independent identity.')
    if not provider_uid or provider_uid != str(evidence.get('provider_uid') or ''):
        raise ValueError('Released provider UID changed; refuse silent Re-adopt identity reuse.')
    release = evidence.get('release_governance') or {}
    if release.get('status') != 'released':
        raise ValueError('Released generation has no verifiable handoff evidence.')
    _require_re_adoption_handback_for_managed_release(
        provider_evidence=evidence,
        release_evidence=release,
        provider_uid=provider_uid,
        resource_version=resource_version,
        namespace=str(tenant.provider_reference or ''),
    )
    return {
        'predecessor_tenant_id': previous.id,
        'predecessor_generation': previous.generation,
        'predecessor_correlation_id': previous.correlation_id,
        'previous_released_at': release.get('released_at'),
        'provider_uid_verified': True,
    }


def _verify_released_namespace_lineage(
    *, cluster_id: str, namespace: str, provider_uid: str, tenant_slug: str,
    resource_version: str | None = None,
) -> None:
    """Refuse ambiguous Tenant reassignment or provider name reuse across Released history."""
    previous = (
        TenantNamespace.query.filter_by(cluster_id=cluster_id, namespace=namespace)
        .filter(TenantNamespace.provisioning_status == TenantNamespaceProvisioningStatus.RELEASED.value)
        .order_by(TenantNamespace.generation.desc()).first()
    )
    if previous is None:
        return
    if previous.environment.tenant.slug != tenant_slug:
        raise ValueError('Released Namespace belongs to another Tenant lineage; ownership review is required.')
    if not provider_uid or provider_uid != previous.provider_reference:
        raise ValueError('Released Namespace UID changed; refuse silent Namespace Re-adopt.')
    _require_re_adoption_handback_for_managed_release(
        provider_evidence=previous.provisioning_evidence_json or {},
        release_evidence=(previous.provisioning_evidence_json or {}).get('release_governance') or {},
        provider_uid=provider_uid, resource_version=resource_version,
    )


def _native_namespace_record(
    context: _AdoptionContext,
    environment: TenantEnvironment,
    *,
    metadata: Any,
    allocation: Mapping[str, Any],
) -> TenantNamespace:
    provider_uid = str(getattr(metadata, 'uid', None) or '').strip()
    resource_version = str(getattr(metadata, 'resource_version', None) or '').strip()
    if not provider_uid or not resource_version:
        raise ValueError('Native Namespace provider UID/resourceVersion is missing.')
    _verify_released_namespace_lineage(
        cluster_id=str(context.cluster.id), namespace=context.resource_name,
        provider_uid=provider_uid, tenant_slug=context.tenant.slug,
        resource_version=resource_version,
    )
    record = TenantNamespace()
    record.environment = environment
    record.cluster_id = context.cluster.id
    record.namespace = context.resource_name
    record.generation = _next_namespace_generation(
        cluster_id=str(context.cluster.id),
        namespace=context.resource_name,
    )
    record.ownership_status = TenantOwnershipStatus.ADOPTED.value
    record.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
    record.provisioning_message = (
        'Adopted Baseline · Observed. Existing Kubernetes allocation is read-only until governance cutover.'
        if allocation['control_state'] == 'observed'
        else 'Adopted Baseline · Control Unavailable. Review ambiguous or unsupported allocation evidence.'
    )
    record.allocation_quota_json = dict(allocation['quota'])
    record.allocation_limit_defaults_json = dict(allocation['limits'])
    record.allocation_storage_policy_json = dict(allocation.get('storage_policy') or {})
    record.allocation_customized = True
    record.desired_hash = None
    record.effective_hash = str(allocation['effective_hash'])
    record.provider_reference = provider_uid
    record.last_reconciled_at = context.now
    record.provisioning_evidence_json = {
        'source': 'tenant_discovery_adoption',
        'provider': 'native_kubernetes',
        'provider_uid': provider_uid,
        'resource_version': resource_version,
        'observed_present': True,
        'adopted_at': context.now.isoformat(),
        'allocation': dict(allocation),
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }
    db.session.add(record)
    return record


def _take_over_native_allocation(context: _AdoptionContext, record: TenantNamespace) -> None:
    allocation = dict((record.provisioning_evidence_json or {}).get('allocation') or {})
    if allocation.get('control_state') != 'observed':
        raise ValueError(
            str(allocation.get('control_reason') or 'Native allocation authority is not safe for managed adoption.')
        )

    profile = _materialize_adopted_baseline_profile(record)
    capacity_decision = enforce_existing_namespace_allocation_preflight(
        record=record,
        profile=profile,
        quota_hard=profile.quota_hard_json or {},
    )
    if str(capacity_decision.decision) != 'allow':
        raise ValueError(
            'Adoption cannot take governance ownership because capacity admission did not allow '
            'the observed provider baseline.'
        )

    reconcile_adopted_native_allocation(
        record,
        profile=profile,
        resource_profile_version=int(profile.version or 1),
        allocation_customized=True,
        capacity_decision_id=capacity_decision.id,
        quota_hard=dict(profile.quota_hard_json or {}),
        limit_defaults=dict(profile.limit_defaults_json or {}),
        storage_policy=dict(profile.storage_policy_json or {}),
        operation='adoption_takeover',
    )
    evidence = dict(context.tenant.provider_evidence_json or {})
    evidence.update(
        {
            'allocation_control_state': 'kaori_managed',
            'allocation_provenance': 'kaori_managed',
            'adoption_takeover': {
                'profile_id': profile.public_id,
                'profile_version': int(profile.version or 1),
                'provider_value_change_requested': False,
                'effective_values_preserved': True,
                'storage_policy': dict(profile.storage_policy_json or {}),
                'provider_mutation_performed': True,
                'provider_readback_verified': record.provisioning_status
                == TenantNamespaceProvisioningStatus.READY.value,
                'taken_over_at': datetime.now(UTC).isoformat(),
            },
            'provider_mutation_performed': True,
        }
    )
    context.tenant.provider_evidence_json = evidence


def _adopt_native(context: _AdoptionContext) -> tuple[TenantEnvironment, TenantNamespace]:
    try:
        item = context.client.core_api().read_namespace(context.resource_name, _request_timeout=5)
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError('The discovered namespace is no longer present in Kubernetes.') from exc
        raise

    metadata = getattr(item, 'metadata', None)
    labels = dict(getattr(metadata, 'labels', None) or {})
    provider_status = _namespace_phase(item)
    management_status, reason = _native_management(
        namespace=context.resource_name,
        labels=labels,
        managed_record=_managed_namespace_map([str(context.cluster.id)]).get(
            (str(context.cluster.id), context.resource_name)
        ),
        owner_references=getattr(metadata, 'owner_references', None),
    )
    if provider_status == 'Terminating':
        raise ValueError('The discovered namespace is terminating and cannot be adopted.')
    if management_status != 'Discovered':
        raise ValueError(reason)

    provider_uid = str(getattr(metadata, 'uid', None) or '').strip()
    resource_version = str(getattr(metadata, 'resource_version', None) or '').strip()
    validate_adoption_provider_identity(
        expected_uid=context.expected_provider_uid,
        observed_uid=provider_uid,
        expected_resource_version=context.expected_provider_resource_version,
        observed_resource_version=resource_version,
    )
    allocation = observe_native_namespace_allocation(context.client.core_api(), context.resource_name)
    tenant = context.tenant
    tenant.provider_key = 'native_kubernetes'
    tenant.provider_state = 'native'
    tenant.reconciliation_authority = 'native_kubernetes'
    tenant.provider_reference = context.resource_name
    tenant.provider_evidence_json = {
        'source': 'tenant_discovery_adoption',
        'provider': 'native_kubernetes',
        'resource_kind': 'Namespace',
        'resource_name': context.resource_name,
        'provider_uid': provider_uid,
        'resource_version': resource_version,
        'adopted_at': context.now.isoformat(),
        'allocation_provenance': 'adopted_observed',
        'allocation_control_state': allocation['control_state'],
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }
    lineage = _released_predecessor_evidence(
        tenant, provider_uid=provider_uid, resource_version=resource_version,
    )
    if lineage is not None:
        tenant.provider_evidence_json['re_adoption_lineage'] = lineage
    db.session.add(tenant)

    environment = TenantEnvironment()
    environment.tenant = tenant
    environment.environment = context.environment_name
    db.session.add(environment)
    record = _native_namespace_record(context, environment, metadata=metadata, allocation=allocation)
    db.session.flush()
    _take_over_native_allocation(context, record)
    return environment, record


def _capsule_namespace_records(
    context: _AdoptionContext,
    environment: TenantEnvironment,
    allocation: Mapping[str, Any],
) -> list[TenantNamespace]:
    correlated_rows = allocation.get('correlated_namespaces')
    if not isinstance(correlated_rows, list):
        raise ValueError('Capsule Namespace correlation inventory is missing or malformed.')
    # Validate the whole provider inventory before constructing any governance
    # record: a late duplicate or missing UID must not allow partial adoption.
    seen_names: set[str] = set()
    for correlated in correlated_rows:
        if not isinstance(correlated, Mapping):
            raise ValueError('Capsule Namespace correlation inventory contains malformed entries.')
        namespace_name = str(correlated.get('name') or '').strip()
        provider_uid = str(correlated.get('uid') or '').strip()
        resource_version = str(correlated.get('resource_version') or '').strip()
        if not namespace_name or not provider_uid or not resource_version:
            raise ValueError('Capsule Namespace adoption requires complete provider name/UID/resourceVersion evidence.')
        if namespace_name in seen_names:
            raise ValueError('Capsule Namespace adoption has ambiguous duplicate Namespace correlation.')
        seen_names.add(namespace_name)

    records: list[TenantNamespace] = []
    for correlated in correlated_rows:
        namespace_name = str(correlated['name']).strip()
        provider_uid = str(correlated['uid']).strip()
        resource_version = str(correlated['resource_version']).strip()
        namespace_allocation = dict(correlated.get('allocation') or {})
        _verify_released_namespace_lineage(
            cluster_id=str(context.cluster.id), namespace=namespace_name,
            provider_uid=provider_uid, tenant_slug=context.tenant.slug,
        )
        record = TenantNamespace()
        record.environment = environment
        record.cluster_id = context.cluster.id
        record.namespace = namespace_name
        record.generation = _next_namespace_generation(
            cluster_id=str(context.cluster.id),
            namespace=namespace_name,
        )
        record.ownership_status = TenantOwnershipStatus.ADOPTED.value
        record.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
        record.provisioning_message = (
            'Adopted · Provider Mirrored Policy. Capsule remains authoritative; supported Namespace '
            'Container/PVC policy is committed in KAORI without claiming controller-owned write authority.'
            if allocation['control_state'] == 'observed'
            else 'Adopted Baseline · Control Unavailable. Capsule allocation authority requires review.'
        )
        record.allocation_quota_json = dict(namespace_allocation.get('quota') or {})
        record.allocation_limit_defaults_json = dict(namespace_allocation.get('limits') or {})
        record.allocation_storage_policy_json = dict(namespace_allocation.get('storage_policy') or {})
        record.allocation_customized = True
        record.desired_hash = None
        record.effective_hash = str(namespace_allocation.get('effective_hash') or '') or None
        record.provider_reference = provider_uid
        record.last_reconciled_at = context.now
        record.provisioning_evidence_json = {
            'source': 'tenant_discovery_adoption',
            'provider': 'capsule',
            'provider_uid': provider_uid,
            'resource_version': resource_version,
            'observed_present': True,
            'adopted_at': context.now.isoformat(),
            'allocation': namespace_allocation,
            'allocation_authority': allocation['allocation_authority'],
            'allocation_control_state': allocation['control_state'],
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }
        db.session.add(record)
        records.append(record)
    return records


def _mirror_capsule_namespace_policies(tenant: Tenant, records: list[TenantNamespace]) -> None:
    for record in records:
        observation_value = (record.provisioning_evidence_json or {}).get('allocation')
        observation = dict(observation_value) if isinstance(observation_value, Mapping) else {}
        if observation.get('unsupported_dimensions') or observation.get('ambiguous_dimensions'):
            raise ValueError(
                f'Namespace/{record.namespace} contains unsupported or ambiguous policy dimensions; '
                'managed adoption fails closed.'
            )
        if not observation.get('limits') and not observation.get('storage_policy'):
            continue

        profile = _materialize_capsule_namespace_policy_profile(tenant, record, observation)
        record.resource_profile = profile
        record.resource_profile_id = profile.id
        record.resource_profile_version = int(profile.version or 1)
        record.allocation_quota_json = {}
        record.allocation_limit_defaults_json = dict(profile.limit_defaults_json or {})
        record.allocation_storage_policy_json = dict(profile.storage_policy_json or {})
        evidence = dict(record.provisioning_evidence_json or {})
        evidence.update(
            {
                'allocation_control_state': 'provider_mirrored_policy',
                'provider_policy_mirror': {
                    'profile_id': profile.public_id,
                    'profile_version': int(profile.version or 1),
                    'authority': 'capsule',
                    'source': 'capsule_generated_namespace_policy',
                    'provider_mutation_performed': False,
                    'mirrored_at': datetime.now(UTC).isoformat(),
                },
            }
        )
        record.provisioning_evidence_json = evidence
        record.provisioning_message = (
            'Capsule-generated Container/PVC policy is mirrored into KAORI. '
            'It is not treated as KAORI drift because no admitted Capsule source-write authority exists.'
        )


def _finalize_capsule_takeover(
    context: _AdoptionContext,
    allocation: Mapping[str, Any],
    records: list[TenantNamespace],
) -> None:
    shared_profile = _take_over_capsule_allocation(
        tenant=context.tenant,
        allocation=allocation,
    )
    evidence = dict(context.tenant.provider_evidence_json or {})
    evidence.update(
        {
            'allocation_control_state': 'kaori_managed',
            'adoption_takeover': {
                'profile_id': shared_profile.public_id if shared_profile is not None else None,
                'profile_version': int(shared_profile.version or 1) if shared_profile is not None else None,
                'provider_value_change_requested': False,
                'effective_values_preserved': True,
                'namespaced_policy_profiles': [
                    record.resource_profile.public_id for record in records if record.resource_profile is not None
                ],
                'provider_mutation_performed': True,
                'taken_over_at': datetime.now(UTC).isoformat(),
            },
            'provider_mutation_performed': True,
        }
    )
    context.tenant.provider_evidence_json = evidence


def _adopt_capsule(context: _AdoptionContext) -> tuple[TenantEnvironment, TenantNamespace | None]:
    capsule_version, item = _read_capsule_tenant(context.client, context.resource_name)
    status = _capsule_phase(item)
    if status == 'Terminating':
        raise ValueError('The Capsule Tenant is terminating and cannot be adopted.')
    if (
        _managed_capsule_map([str(context.cluster.id)]).get((str(context.cluster.id), context.resource_name))
        is not None
    ):
        raise ValueError('This Capsule Tenant is already governed by KAORI.')

    metadata = item.get('metadata') or {}
    provider_labels = metadata.get('labels') or {}
    if not isinstance(provider_labels, Mapping):
        raise ValueError('Capsule Tenant ownership labels are malformed.')
    ownership_reason = _unclaimed_provider_ownership_reason(
        labels=provider_labels, resource_kind='Capsule Tenant',
    )
    if ownership_reason:
        raise ValueError(ownership_reason)
    provider_uid = str(metadata.get('uid') or '').strip()
    resource_version = str(metadata.get('resourceVersion') or '').strip()
    validate_adoption_provider_identity(
        expected_uid=context.expected_provider_uid,
        observed_uid=provider_uid,
        expected_resource_version=context.expected_provider_resource_version,
        observed_resource_version=resource_version,
    )
    allocation = observe_capsule_tenant_allocation(
        context.client,
        tenant_name=context.resource_name,
        tenant_item=item,
    )
    provider_state, capability_evidence = qualify_capsule_tenant_adoption(
        cluster=context.cluster,
        api_version=capsule_version,
        tenant_name=context.resource_name,
        resource_version=resource_version or None,
    )
    _apply_capsule_allocation_capability_state(
        allocation,
        provider_state=provider_state,
        capability_evidence=capability_evidence,
    )

    # The Capsule controller may report Namespaces already governed through
    # Native or another Capsule Tenant. Never reparent such Namespace records
    # simply because the discovered Capsule Tenant CR itself is ungoverned.
    existing_namespaces = _managed_namespace_map([str(context.cluster.id)])
    for row in allocation.get('correlated_namespaces') or []:
        if not isinstance(row, Mapping):
            raise ValueError('Capsule Namespace correlation inventory contains malformed entries.')
        namespace_name = str(row.get('name') or '').strip()
        if namespace_name and (str(context.cluster.id), namespace_name) in existing_namespaces:
            raise ValueError('Capsule Namespace already belongs to a governed KAORI Tenant.')

    tenant = context.tenant
    tenant.provider_key = 'capsule'
    tenant.provider_state = provider_state
    tenant.reconciliation_authority = 'capsule'
    tenant.provider_reference = context.resource_name
    tenant.provider_evidence_json = {
        'source': 'tenant_discovery_adoption',
        'provider': 'capsule',
        'provider_api_version': capsule_version,
        'resource_kind': 'Tenant',
        'resource_name': context.resource_name,
        'provider_uid': provider_uid,
        'resource_version': resource_version,
        'provider_status': status,
        'adopted_at': context.now.isoformat(),
        'allocation_baseline': allocation,
        'allocation_provenance': 'adopted_observed',
        'allocation_control_state': allocation['control_state'],
        'capsule': capability_evidence,
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }
    lineage = _released_predecessor_evidence(tenant, provider_uid=provider_uid)
    if lineage is not None:
        tenant.provider_evidence_json['re_adoption_lineage'] = lineage
    db.session.add(tenant)
    environment = TenantEnvironment()
    environment.tenant = tenant
    environment.environment = context.environment_name
    db.session.add(environment)
    db.session.flush()

    records = _capsule_namespace_records(context, environment, allocation)
    _mirror_capsule_namespace_policies(tenant, records)
    _finalize_capsule_takeover(context, allocation, records)
    return environment, records[0] if records else None


def validate_existing_tenant_attachment_target(
    tenant: Tenant, *, cluster_id: str, namespace: str
) -> None:
    if not namespace or str(tenant.cluster_id) != cluster_id:
        raise ValueError('Namespace and existing Tenant must belong to the same cluster.')
    if (
        tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
    ):
        raise ValueError('The selected Tenant is not Ready under Native Kubernetes authority.')


def validate_namespace_attachment_uid(*, observed_uid: str, expected_uid: str) -> None:
    if not observed_uid or not expected_uid or observed_uid != expected_uid:
        raise ValueError('Namespace UID changed since adoption preflight; refresh Discovery.')


def attach_discovered_native_namespace_committed(
    source: Mapping[str, Any],
) -> tuple[Tenant, TenantEnvironment, TenantNamespace]:
    """Adopt a discovered Native Namespace into an existing governed Tenant.

    Provider/UID/manager/capacity validation is repeated live. The existing
    Tenant identity and original adoption lineage must not be overwritten.
    """
    if str(source.get('provider_key') or '') != 'native_kubernetes':
        raise ValueError('Existing-Tenant Namespace adoption supports Native Kubernetes only.')
    environment_id = str(source.get('attach_environment_id') or '')
    if not environment_id.isdecimal():
        raise ValueError('Select a valid existing Tenant environment.')
    environment = db.session.get(TenantEnvironment, int(environment_id))
    if environment is None:
        raise ValueError('The selected Tenant environment no longer exists.')
    tenant = environment.tenant
    cluster_id = str(source.get('cluster_id') or '').strip()
    namespace = str(source.get('resource_name') or '').strip()
    validate_existing_tenant_attachment_target(tenant, cluster_id=cluster_id, namespace=namespace)

    cluster = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(Cluster.id == tenant.cluster_id, Cluster.status == ClusterStatus.CONNECTED.value)
        .first()
    )
    if cluster is None or not tenant_workspace_connection_available(cluster.kubernetes_connection):
        raise ValueError('The selected Kubernetes cluster is not available for adoption.')
    context = _AdoptionContext(
        cluster=cluster,
        client=runtime_adapter.build_client(cluster),
        provider_key='native_kubernetes',
        resource_name=namespace,
        environment_name=environment.environment,
        tenant=tenant,
        now=datetime.now(UTC),
    )
    try:
        item = context.client.core_api().read_namespace(namespace, _request_timeout=5)
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError('The Namespace was removed before attachment.') from exc
        raise
    metadata = getattr(item, 'metadata', None)
    provider_uid = str(getattr(metadata, 'uid', '') or '').strip()
    expected_uid = str(source.get('provider_uid') or '').strip()
    validate_namespace_attachment_uid(observed_uid=provider_uid, expected_uid=expected_uid)
    validate_adoption_provider_identity(
        expected_uid=expected_uid, observed_uid=provider_uid,
        expected_resource_version=str(source.get('provider_resource_version') or '').strip(),
        observed_resource_version=str(getattr(metadata, 'resource_version', None) or '').strip(),
    )
    status, reason = _native_management(
        namespace=namespace,
        labels=dict(getattr(metadata, 'labels', None) or {}),
        managed_record=_managed_namespace_map([cluster_id]).get((cluster_id, namespace)),
        owner_references=getattr(metadata, 'owner_references', None),
    )
    if _namespace_phase(item) == 'Terminating' or status != 'Discovered':
        raise ValueError('Namespace attachment is blocked: ' + reason)

    allocation = observe_native_namespace_allocation(context.client.core_api(), namespace)
    existing_evidence = dict(tenant.provider_evidence_json or {})
    try:
        record = _native_namespace_record(context, environment, metadata=metadata, allocation=allocation)
        db.session.flush()
        _take_over_native_allocation(context, record)
        # Attachment is Namespace-scoped; do not rewrite the existing Tenant's
        # top-level provenance/authority as though it had been newly adopted.
        tenant.provider_evidence_json = existing_evidence
        namespace_evidence = dict(record.provisioning_evidence_json or {})
        namespace_evidence['attachment'] = {
            'tenant_id': tenant.id,
            'tenant_generation': tenant.generation,
            'environment': environment.environment,
            'provider_uid': provider_uid,
            'source': 'governed_existing_tenant_attachment',
            'attached_at': datetime.now(UTC).isoformat(),
            'grants_expanded_automatically': False,
        }
        record.provisioning_evidence_json = namespace_evidence
        db.session.commit()
        return tenant, environment, record
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Namespace attachment conflicted with committed governance state.') from exc
    except Exception:
        db.session.rollback()
        raise


def attach_discovered_capsule_namespace_committed(
    source: Mapping[str, Any],
) -> tuple[Tenant, TenantEnvironment, TenantNamespace]:
    """Attach a provider-correlated Capsule Namespace to an existing Capsule Tenant.

    Does not create a new Tenant, rewrite the Capsule Tenant CR, or grant access.
    Provider UID, namespace membership and policies are checked live on submit.
    """
    if str(source.get('provider_key') or '') != 'capsule':
        raise ValueError('Capsule Namespace attachment requires Capsule provider authority.')
    environment_id = str(source.get('attach_environment_id') or '').strip()
    if not environment_id.isdecimal():
        raise ValueError('Select an existing Capsule Tenant environment.')
    environment = db.session.get(TenantEnvironment, int(environment_id))
    if environment is None:
        raise ValueError('The selected Capsule Tenant environment is missing.')
    tenant = environment.tenant
    # Discovery includes provider scope; Registry derives it from the committed
    # destination Environment. Never trust an arbitrary cross-cluster reparent.
    cluster_id = str(source.get('cluster_id') or tenant.cluster_id).strip()
    namespace = str(source.get('resource_name') or '').strip()
    capsule_name = str(source.get('capsule_tenant_name') or tenant.provider_reference or '').strip()
    if (
        not namespace or namespace in {'default', 'kube-system', 'kube-public', 'kube-node-lease'}
        or str(tenant.cluster_id) != cluster_id
        or tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.provider_key != 'capsule'
        or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or not capsule_name or capsule_name != str(tenant.provider_reference or '')
    ):
        raise ValueError('Capsule Namespace attachment does not match a healthy governed Tenant.')

    cluster = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(Cluster.id == cluster_id, Cluster.status == ClusterStatus.CONNECTED.value)
        .first()
    )
    if cluster is None or not tenant_workspace_connection_available(cluster.kubernetes_connection):
        raise ValueError('Capsule cluster connection is unavailable.')
    if _managed_namespace_map([cluster_id]).get((cluster_id, namespace)) is not None:
        raise ValueError('Namespace already has a committed KAORI governance owner.')

    client = runtime_adapter.build_client(cluster)
    _version, tenant_cr = _read_capsule_tenant(client, capsule_name)
    if _capsule_phase(tenant_cr) == 'Terminating':
        raise ValueError('Capsule Tenant is terminating; attachment is blocked.')
    cr_metadata = tenant_cr.get('metadata') or {}
    expected_tenant_uid = str((tenant.provider_evidence_json or {}).get('provider_uid') or '')
    if (
        not expected_tenant_uid
        or str(cr_metadata.get('uid') or '') != expected_tenant_uid
        or not cr_metadata.get('resourceVersion')
    ):
        raise ValueError('Capsule Tenant CR identity differs from committed KAORI authority.')

    allocation = observe_capsule_tenant_allocation(
        client, tenant_name=capsule_name, tenant_item=tenant_cr,
    )
    selected = select_capsule_namespace_attachment_candidate(
        allocation, namespace=namespace, capsule_tenant_name=capsule_name,
        expected_uid=str(source.get('provider_uid') or '').strip(),
        expected_resource_version=str(source.get('provider_resource_version') or '').strip(),
    )
    # Both immutable UID and preflight resourceVersion are mandatory for
    # attachment; empty request fields must never skip correlation checks.
    if not str(source.get('provider_uid') or '').strip() or not str(
        source.get('provider_resource_version') or ''
    ).strip():
        raise ValueError('Capsule attachment requires fresh Namespace UID/resourceVersion evidence.')

    # Provider listing/candidate selection is not a final authority proof.
    # Independently re-read the exact Namespace object and its Capsule CR,
    # including ownerReferences (and owner UID), before any KAORI DB commit.
    observed_namespace = client.core_api().read_namespace(
        namespace, _request_timeout=5
    )
    proof = validate_capsule_namespace_attachment(
        tenant=tenant, cluster_id=cluster_id, capsule_item=tenant_cr,
        namespace=observed_namespace,
        expected_namespace_uid=str(source['provider_uid']).strip(),
        status_namespace_names=_capsule_status_namespace_names(tenant_cr),
    )
    if (
        proof['namespace'] != namespace
        or proof['namespace_uid'] != selected['uid']
        or proof['namespace_resource_version'] != selected['resource_version']
    ):
        raise ValueError('Capsule Namespace changed after Discovery review.')

    _, verified_tenant_cr = _read_capsule_tenant(client, capsule_name)
    verified_metadata = verified_tenant_cr.get('metadata') or {}
    if (
        str(verified_metadata.get('uid') or '') != proof['capsule_tenant_uid']
        or str(verified_metadata.get('resourceVersion') or '')
        != proof['capsule_tenant_resource_version']
    ):
        raise ValueError('Capsule Tenant CR changed during attachment; repeat Discovery.')
    verified_namespace = client.core_api().read_namespace(namespace, _request_timeout=5)
    verified_namespace_meta = getattr(verified_namespace, 'metadata', None)
    if (
        str(getattr(verified_namespace_meta, 'uid', '') or '') != proof['namespace_uid']
        or str(getattr(verified_namespace_meta, 'resource_version', '') or '')
        != proof['namespace_resource_version']
    ):
        raise ValueError('Capsule Namespace changed during attachment; repeat Discovery.')

    context = _AdoptionContext(
        cluster=cluster, client=client, provider_key='capsule',
        resource_name=namespace, environment_name=environment.environment,
        tenant=tenant, now=datetime.now(UTC),
    )
    previous_evidence = dict(tenant.provider_evidence_json or {})
    try:
        scoped = {**allocation, 'correlated_namespaces': [selected]}
        records = _capsule_namespace_records(context, environment, scoped)
        if len(records) != 1:
            raise ValueError('Capsule Namespace attachment did not yield one canonical record.')
        _mirror_capsule_namespace_policies(tenant, records)
        record = records[0]
        evidence = dict(record.provisioning_evidence_json or {})
        evidence['attachment'] = {
            'tenant_id': tenant.id,
            'tenant_generation': tenant.generation,
            'environment': environment.environment,
            'capsule_tenant': capsule_name,
            'capsule_uid': expected_tenant_uid,
            'capsule_authority': proof,
            'provider_uid': selected['uid'],
            'provider_resource_version': selected['resource_version'],
            'source': 'governed_capsule_existing_tenant_attachment',
            'attached_at': context.now.isoformat(),
            'provider_mutation_performed': False,
            'grants_expanded_automatically': False,
        }
        record.provisioning_evidence_json = evidence
        # Capsule CR remains authoritative; attaching one Namespace does not
        # reconfigure Tenant-wide quota, ownership, or existing membership.
        tenant.provider_evidence_json = previous_evidence
        db.session.commit()
        return tenant, environment, record
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Capsule Namespace already has a committed governance generation.') from exc
    except Exception:
        db.session.rollback()
        raise


def adopt_discovered_tenant_committed(
    source: Mapping[str, Any],
) -> tuple[Tenant, TenantEnvironment, TenantNamespace | None]:
    """Adopt provider state and perform governed takeover without changing effective values."""

    try:
        context = _prepare_adoption(source)
        if context.provider_key == 'native_kubernetes':
            environment, namespace_record = _adopt_native(context)
        else:
            environment, namespace_record = _adopt_capsule(context)

        db.session.commit()
        return context.tenant, environment, namespace_record
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Tenant adoption conflicted with committed KAORI state. Refresh Discovery and retry.') from exc
    except Exception:
        # Provider writes cannot be rolled back by a database transaction.
        # Clear all pending governance records before the route records an
        # operational failure; never accidentally commit a partial adoption.
        db.session.rollback()
        raise
