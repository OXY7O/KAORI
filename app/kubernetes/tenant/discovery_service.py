from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_observation import (
    observe_capsule_tenant_allocation,
    observe_native_namespace_allocation,
)
from app.kubernetes.tenant.capsule_provider import discover_capsule
from app.kubernetes.tenant.capsule_tenant import qualify_capsule_tenant_adoption
from app.models import Cluster
from app.models.cluster import ClusterStatus
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantEnvironmentName,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantOwnershipStatus,
)

_SYSTEM_NAMESPACES = frozenset({'default', 'kube-system', 'kube-public', 'kube-node-lease'})
_CAPSULE_GROUP = 'capsule.clastix.io'
_CAPSULE_VERSIONS = ('v1beta2', 'v1beta1')


def _namespace_phase(item: Any) -> str:
    metadata = getattr(item, 'metadata', None)
    status = getattr(item, 'status', None)
    if getattr(metadata, 'deletion_timestamp', None):
        return 'Terminating'
    return str(getattr(status, 'phase', None) or 'Present')


def _capsule_phase(item: dict[str, Any]) -> str:
    metadata = item.get('metadata') if isinstance(item, dict) else {}
    status = item.get('status') if isinstance(item, dict) else {}
    if isinstance(metadata, dict) and metadata.get('deletionTimestamp'):
        return 'Terminating'
    if isinstance(status, dict):
        for key in ('state', 'phase'):
            value = status.get(key)
            if value:
                return str(value)
        conditions = status.get('conditions')
        if isinstance(conditions, list):
            for condition in conditions:
                if not isinstance(condition, dict):
                    continue
                if condition.get('status') == 'True' and condition.get('type'):
                    return str(condition['type'])
    return 'Observed'


def _tone(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {'active', 'ready', 'observed', 'present'}:
        return 'normal'
    if normalized in {'terminating', 'degraded', 'failed', 'error'}:
        return 'critical'
    return 'warning'


def _native_management(
    *,
    namespace: str,
    labels: dict[str, str],
    managed_record: TenantNamespace | None,
) -> tuple[str, str]:
    if managed_record is not None:
        return 'Managed', 'Already governed by KAORI.'
    if namespace in _SYSTEM_NAMESPACES:
        return 'Blocked', 'Kubernetes system namespaces are not Tenant adoption candidates.'
    external_manager = str(labels.get('app.kubernetes.io/managed-by') or '').strip()
    if external_manager and external_manager.lower() != 'kaori':
        return 'Blocked', f'Provider resource declares external manager {external_manager}.'
    return 'Discovered', 'Candidate for governed adoption preflight; no provider mutation has occurred.'


def _managed_namespace_map(cluster_ids: list[str]) -> dict[tuple[str, str], TenantNamespace]:
    if not cluster_ids:
        return {}
    rows = (
        TenantNamespace.query.filter(
            TenantNamespace.cluster_id.in_(cluster_ids),
            TenantNamespace.provisioning_status != 'deprovisioned',
        )
        .join(TenantEnvironment, TenantNamespace.tenant_environment_id == TenantEnvironment.id)
        .join(Tenant, TenantEnvironment.tenant_id == Tenant.id)
        .all()
    )
    return {(str(item.cluster_id), item.namespace): item for item in rows}


def _managed_capsule_map(cluster_ids: list[str]) -> dict[tuple[str, str], Tenant]:
    if not cluster_ids:
        return {}
    rows = Tenant.query.filter(
        Tenant.cluster_id.in_(cluster_ids),
        Tenant.provider_key == 'capsule',
        Tenant.lifecycle_status != 'decommissioned',
    ).all()
    result: dict[tuple[str, str], Tenant] = {}
    for tenant in rows:
        for reference in {str(tenant.provider_reference or '').strip(), tenant.slug, tenant.name}:
            if reference:
                result[(str(tenant.cluster_id), reference)] = tenant
    return result


def _capsule_items(client) -> tuple[str | None, list[dict[str, Any]]]:
    api = client.custom_objects_api()
    for version in _CAPSULE_VERSIONS:
        try:
            payload = api.list_cluster_custom_object(
                _CAPSULE_GROUP,
                version,
                'tenants',
                _request_timeout=5,
            )
        except ApiException as exc:
            if exc.status == 404:
                continue
            raise
        items = payload.get('items') if isinstance(payload, dict) else None
        return version, [item for item in (items or []) if isinstance(item, dict)]
    return None, []


def _apply_capsule_allocation_capability_state(
    allocation: dict[str, Any],
    *,
    provider_state: str,
    capability_evidence: Mapping[str, Any],
    preview_only: bool = False,
) -> None:
    capabilities = capability_evidence.get('capabilities')
    capabilities = capabilities if isinstance(capabilities, Mapping) else {}
    if not preview_only and provider_state != 'capsule':
        return
    if allocation.get('authority_unsupported_dimensions') or allocation.get('authority_ambiguous_dimensions'):
        return

    authority = str(allocation.get('allocation_authority') or '')
    capability = ''
    label = ''
    if authority == 'capsule_global_resource_quota':
        capability = 'shared_global_quota'
        label = 'Capsule GlobalResourceQuota'
    elif authority == 'capsule_tenant_resource_quotas':
        capability = 'tenant_resource_quotas'
        label = 'Capsule Tenant.spec.resourceQuotas'
    if not capability or str(capabilities.get(capability) or '') != 'available':
        return

    allocation['control_state'] = 'observed'
    allocation['control_reason'] = (
        (
            f'{label} authority and the {capability} CRD/schema capability are observed. '
            'Adoption revalidates the admission path before committing governance evidence.'
        )
        if preview_only
        else (
            f'{label} authority is observed and the {capability} capability is admitted. '
            'Provider state remains read-only until explicit governance cutover.'
        )
    )
    allocation['admitted_capability'] = capability if not preview_only else None
    allocation['capability_preview'] = capability if preview_only else None


def get_tenant_discovery_context(
    *,
    page: int = 1,
    per_page: int = 5,
    cluster_id: str = '',
    provider: str = '',
    management: str = '',
    search: str = '',
) -> dict[str, Any]:
    """Live, read-only provider discovery for the two-way Tenant Registry lane."""

    normalized_cluster = cluster_id.strip()
    normalized_provider = provider.strip().lower()
    normalized_management = management.strip().lower()
    normalized_search = search.strip().lower()

    query = Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
    if normalized_cluster:
        query = query.filter(Cluster.id == normalized_cluster)
    clusters = query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    cluster_ids = [str(cluster.id) for cluster in clusters]
    managed_namespaces = _managed_namespace_map(cluster_ids)
    managed_capsule = _managed_capsule_map(cluster_ids)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    checked_at = datetime.now(UTC)

    for cluster in clusters:
        cluster_key = str(cluster.id)
        try:
            client = runtime_adapter.build_client(cluster)
            namespace_items = cast(Any, client.core_api().list_namespace(_request_timeout=5)).items or []
        except Exception:
            errors.append(
                {
                    'cluster_id': cluster_key,
                    'cluster_name': cluster.name,
                    'message': 'Live Kubernetes namespace discovery failed.',
                }
            )
            continue

        observed_native_names: set[str] = set()
        for item in namespace_items:
            metadata = getattr(item, 'metadata', None)
            name = str(getattr(metadata, 'name', None) or '').strip()
            if not name:
                continue
            observed_native_names.add(name)
            raw_labels = getattr(metadata, 'labels', None)
            labels = dict(raw_labels) if isinstance(raw_labels, Mapping) else {}
            managed_record = managed_namespaces.get((cluster_key, name))
            provider_status = _namespace_phase(item)
            management_status, eligibility = _native_management(
                namespace=name,
                labels=labels,
                managed_record=managed_record,
            )
            if managed_record is None and provider_status == 'Terminating':
                management_status = 'Blocked'
                eligibility = 'Namespace is terminating and cannot enter governed adoption.'
            tenant = managed_record.environment.tenant if managed_record is not None else None
            rows.append(
                {
                    'cluster': cluster,
                    'cluster_id': cluster_key,
                    'provider_key': 'native_kubernetes',
                    'provider_label': 'Native Kubernetes',
                    'resource_kind': 'Namespace',
                    'resource_name': name,
                    'provider_status': provider_status,
                    'provider_tone': _tone(provider_status),
                    'management_status': management_status,
                    'management_tone': 'normal'
                    if management_status == 'Managed'
                    else ('info' if management_status == 'Discovered' else 'warning'),
                    'tenant_name': tenant.name if tenant is not None else None,
                    'tenant_id': tenant.id if tenant is not None else None,
                    'eligibility': eligibility,
                    'provider_reference': str(getattr(metadata, 'uid', None) or name),
                }
            )

        for (managed_cluster_id, namespace_name), managed_record in managed_namespaces.items():
            if managed_cluster_id != cluster_key or namespace_name in observed_native_names:
                continue
            tenant = managed_record.environment.tenant
            rows.append(
                {
                    'cluster': cluster,
                    'cluster_id': cluster_key,
                    'provider_key': 'native_kubernetes',
                    'provider_label': 'Native Kubernetes',
                    'resource_kind': 'Namespace',
                    'resource_name': namespace_name,
                    'provider_status': 'Missing',
                    'provider_tone': 'critical',
                    'management_status': 'Managed',
                    'management_tone': 'critical',
                    'tenant_name': tenant.name,
                    'tenant_id': tenant.id,
                    'eligibility': (
                        'Committed KAORI ownership exists, but the Namespace is missing from the live provider. '
                        'Adoption is not applicable; review drift, restore/reconcile, or decommission.'
                    ),
                    'provider_reference': managed_record.provider_reference or namespace_name,
                }
            )

        try:
            capsule_version, capsule_items = _capsule_items(client)
        except Exception:
            errors.append(
                {
                    'cluster_id': cluster_key,
                    'cluster_name': cluster.name,
                    'message': 'Live Capsule Tenant discovery failed.',
                }
            )
            capsule_version, capsule_items = None, []

        observed_capsule_names: set[str] = set()
        for item in capsule_items:
            metadata = item.get('metadata') or {}
            name = str(metadata.get('name') or '').strip()
            if not name:
                continue
            observed_capsule_names.add(name)
            tenant = managed_capsule.get((cluster_key, name))
            status = _capsule_phase(item)
            management_status = (
                'Managed' if tenant is not None else ('Blocked' if status == 'Terminating' else 'Discovered')
            )
            rows.append(
                {
                    'cluster': cluster,
                    'cluster_id': cluster_key,
                    'provider_key': 'capsule',
                    'provider_label': 'Capsule',
                    'resource_kind': 'Tenant CR',
                    'resource_name': name,
                    'provider_status': status,
                    'provider_tone': _tone(status),
                    'management_status': management_status,
                    'management_tone': (
                        'normal'
                        if management_status == 'Managed'
                        else ('info' if management_status == 'Discovered' else 'warning')
                    ),
                    'tenant_name': tenant.name if tenant is not None else None,
                    'tenant_id': tenant.id if tenant is not None else None,
                    'eligibility': (
                        'Already governed by KAORI.'
                        if tenant is not None
                        else (
                            'Capsule Tenant is terminating and cannot be adopted.'
                            if management_status == 'Blocked'
                            else 'Candidate for governed Capsule adoption preflight; provider authority remains Capsule.'
                        )
                    ),
                    'provider_reference': str(metadata.get('uid') or name),
                    'provider_api_version': capsule_version,
                }
            )

        managed_capsule_tenants = {
            tenant.id: tenant
            for (managed_cluster_id, _reference), tenant in managed_capsule.items()
            if managed_cluster_id == cluster_key
        }
        for tenant in managed_capsule_tenants.values():
            reference = str(tenant.provider_reference or tenant.slug or tenant.name).strip()
            if not reference or reference in observed_capsule_names:
                continue
            evidence = tenant.provider_evidence_json or {}
            rows.append(
                {
                    'cluster': cluster,
                    'cluster_id': cluster_key,
                    'provider_key': 'capsule',
                    'provider_label': 'Capsule',
                    'resource_kind': 'Tenant CR',
                    'resource_name': reference,
                    'provider_status': 'Missing',
                    'provider_tone': 'critical',
                    'management_status': 'Managed',
                    'management_tone': 'critical',
                    'tenant_name': tenant.name,
                    'tenant_id': tenant.id,
                    'eligibility': (
                        'KAORI still governs this Tenant, but the authoritative Capsule Tenant CR is missing. '
                        'Adoption is not applicable; restore provider state or use governed recovery/decommission.'
                    ),
                    'provider_reference': reference,
                    'provider_api_version': str(evidence.get('provider_api_version') or '') or capsule_version,
                }
            )

    if normalized_provider:
        rows = [row for row in rows if row['provider_key'] == normalized_provider]
    if normalized_management:
        rows = [row for row in rows if row['management_status'].lower() == normalized_management]
    if normalized_search:
        rows = [
            row
            for row in rows
            if normalized_search in str(row['resource_name']).lower()
            or normalized_search in str(row.get('tenant_name') or '').lower()
            or normalized_search in str(row['cluster'].name).lower()
        ]

    rows.sort(
        key=lambda row: (
            0 if row['management_status'] == 'Discovered' else 1,
            str(row['cluster'].name).lower(),
            str(row['provider_label']).lower(),
            str(row['resource_name']).lower(),
        )
    )
    visible_rows, pagination = paginate_sequence(rows, page=page, per_page=per_page)

    return {
        'tenant_discovery_rows': visible_rows,
        'tenant_discovery_pagination': pagination,
        'tenant_discovery_filters': {
            'cluster_id': normalized_cluster,
            'provider': normalized_provider,
            'management': normalized_management,
            'search': search.strip(),
        },
        'tenant_discovery_cluster_options': (
            Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
            .order_by(Cluster.name.asc())
            .all()
        ),
        'tenant_discovery_checked_at': present_user_datetime(checked_at),
        'tenant_discovery_errors': errors,
        'tenant_discovery_total': len(rows),
    }


def get_tenant_adoption_preflight_context(
    *,
    cluster_id: str,
    provider_key: str,
    resource_name: str,
) -> dict[str, Any]:
    """Build one deep, live Adoption Preflight only after explicit operator review."""

    normalized_cluster = str(cluster_id or '').strip()
    normalized_provider = str(provider_key or '').strip().lower()
    normalized_resource = str(resource_name or '').strip()
    if normalized_provider not in {'native_kubernetes', 'capsule'}:
        raise ValueError('Unsupported Tenant discovery provider.')
    if not normalized_cluster or not normalized_resource:
        raise ValueError('Select a discovered provider object.')

    cluster = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(Cluster.id == normalized_cluster)
        .first()
    )
    if cluster is None:
        raise ValueError('The selected Kubernetes cluster is no longer available.')

    client = runtime_adapter.build_client(cluster)

    if normalized_provider == 'native_kubernetes':
        try:
            item = client.core_api().read_namespace(normalized_resource, _request_timeout=5)
        except ApiException as exc:
            if exc.status == 404:
                raise ValueError('The discovered namespace is no longer present in Kubernetes.') from exc
            raise

        metadata = getattr(item, 'metadata', None)
        labels = dict(getattr(metadata, 'labels', None) or {})
        managed_record = _managed_namespace_map([normalized_cluster]).get(
            (normalized_cluster, normalized_resource)
        )
        provider_status = _namespace_phase(item)
        management_status, eligibility = _native_management(
            namespace=normalized_resource,
            labels=labels,
            managed_record=managed_record,
        )
        if managed_record is None and provider_status == 'Terminating':
            management_status = 'Blocked'
            eligibility = 'Namespace is terminating and cannot enter governed adoption.'
        if management_status != 'Discovered':
            raise ValueError(eligibility)

        allocation = observe_native_namespace_allocation(
            client.core_api(),
            normalized_resource,
        )
        row = {
            'cluster': cluster,
            'cluster_id': normalized_cluster,
            'provider_key': 'native_kubernetes',
            'provider_label': 'Native Kubernetes',
            'resource_kind': 'Namespace',
            'resource_name': normalized_resource,
            'provider_status': provider_status,
            'provider_tone': _tone(provider_status),
            'management_status': management_status,
            'management_tone': 'info',
            'tenant_name': None,
            'tenant_id': None,
            'eligibility': eligibility,
            'provider_reference': str(getattr(metadata, 'uid', None) or normalized_resource),
            'allocation_preflight': allocation,
        }
    else:
        capsule_version, item = _read_capsule_tenant(client, normalized_resource)
        tenant = _managed_capsule_map([normalized_cluster]).get(
            (normalized_cluster, normalized_resource)
        )
        provider_status = _capsule_phase(item)
        management_status = (
            'Managed'
            if tenant is not None
            else ('Blocked' if provider_status == 'Terminating' else 'Discovered')
        )
        eligibility = (
            'Already governed by KAORI.'
            if tenant is not None
            else (
                'Capsule Tenant is terminating and cannot be adopted.'
                if management_status == 'Blocked'
                else 'Candidate for governed Capsule adoption preflight; provider authority remains Capsule.'
            )
        )
        if management_status != 'Discovered':
            raise ValueError(eligibility)

        allocation = observe_capsule_tenant_allocation(
            client,
            tenant_name=normalized_resource,
            tenant_item=item,
        )
        capsule_snapshot = discover_capsule(client.custom_objects_api().api_client)
        capsule_capability_evidence = capsule_snapshot.as_dict()
        _apply_capsule_allocation_capability_state(
            allocation,
            provider_state='preview',
            capability_evidence=capsule_capability_evidence,
            preview_only=True,
        )
        metadata = item.get('metadata') or {}
        row = {
            'cluster': cluster,
            'cluster_id': normalized_cluster,
            'provider_key': 'capsule',
            'provider_label': 'Capsule',
            'resource_kind': 'Tenant CR',
            'resource_name': normalized_resource,
            'provider_status': provider_status,
            'provider_tone': _tone(provider_status),
            'management_status': management_status,
            'management_tone': 'info',
            'tenant_name': None,
            'tenant_id': None,
            'eligibility': eligibility,
            'provider_reference': str(metadata.get('uid') or normalized_resource),
            'provider_api_version': capsule_version,
            'allocation_preflight': allocation,
            'capsule_capability_preflight': capsule_capability_evidence,
        }

    return {
        'tenant_adoption_row': row,
        'tenant_adoption_checked_at': present_user_datetime(datetime.now(UTC)),
    }


def _adoption_environment(value: str) -> str:
    normalized = str(value or '').strip().lower()
    allowed = {item.value for item in TenantEnvironmentName}
    if normalized not in allowed:
        raise ValueError('Select a supported Tenant environment for adoption.')
    return normalized


def _next_tenant_generation(*, cluster_id: str, slug: str) -> int:
    prior = (
        Tenant.query.filter_by(cluster_id=cluster_id, slug=slug)
        .order_by(Tenant.generation.desc(), Tenant.created_at.desc())
        .all()
    )
    if any(item.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value for item in prior):
        raise ValueError('An active KAORI Tenant with this name/slug already exists on the selected cluster.')
    return max((int(item.generation or 1) for item in prior), default=0) + 1


def _next_namespace_generation(*, cluster_id: str, namespace: str) -> int:
    prior = (
        TenantNamespace.query.filter_by(cluster_id=cluster_id, namespace=namespace)
        .order_by(TenantNamespace.generation.desc(), TenantNamespace.created_at.desc())
        .all()
    )
    if any(item.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value for item in prior):
        raise ValueError('This namespace is already represented by an active KAORI Tenant record.')
    return max((int(item.generation or 1) for item in prior), default=0) + 1


def _read_capsule_tenant(client, name: str) -> tuple[str, dict[str, Any]]:
    api = client.custom_objects_api()
    for version in _CAPSULE_VERSIONS:
        try:
            item = api.get_cluster_custom_object(
                _CAPSULE_GROUP,
                version,
                'tenants',
                name,
                _request_timeout=5,
            )
        except ApiException as exc:
            if exc.status == 404:
                continue
            raise
        if isinstance(item, dict):
            return version, item
    raise ValueError('The Capsule Tenant is no longer present in the provider.')


def _materialize_capsule_adoption_profile(
    tenant: Tenant,
    allocation: Mapping[str, Any],
):
    from app.models.tenant import TenantResourceProfile, TenantResourceProfileClass

    quota = dict(allocation.get('shared_quota') or {})
    profile = TenantResourceProfile()
    profile.name = f'Adopted {tenant.name} Allocation · {tenant.id}'
    profile.profile_class = TenantResourceProfileClass.CUSTOM.value
    profile.version = 1
    profile.description = (
        'Provider-equivalent Capsule allocation baseline imported during managed adoption. '
        'Effective provider values are preserved while KAORI takes governance ownership.'
    )
    profile.quota_hard_json = quota
    profile.limit_defaults_json = {}
    profile.storage_policy_json = {}
    profile.advanced_controls_json = {}
    profile.enabled = True
    db.session.add(profile)
    db.session.flush()
    return profile


def _materialize_capsule_namespace_policy_profile(
    tenant: Tenant,
    record: TenantNamespace,
    observation: Mapping[str, Any],
):
    from app.models.tenant import TenantResourceProfile, TenantResourceProfileClass

    profile = TenantResourceProfile()
    profile.name = f'Adopted {tenant.name}/{record.namespace} Policy · {record.id}'
    profile.profile_class = TenantResourceProfileClass.CUSTOM.value
    profile.version = 1
    profile.description = (
        'Provider-equivalent namespaced Container/PVC policy imported during Capsule adoption. '
        'Capsule remains authoritative for Tenant quota.'
    )
    profile.quota_hard_json = {}
    profile.limit_defaults_json = dict(observation.get('limits') or {})
    profile.storage_policy_json = dict(observation.get('storage_policy') or {})
    profile.advanced_controls_json = {}
    profile.enabled = True
    db.session.add(profile)
    db.session.flush()
    return profile


def _take_over_capsule_allocation(
    *,
    tenant: Tenant,
    allocation: Mapping[str, Any],
):
    authority = str(allocation.get('allocation_authority') or '')
    shared_quota = dict(allocation.get('shared_quota') or {})

    if authority == 'none_observed' and not shared_quota:
        return None
    if authority not in {'capsule_global_resource_quota', 'capsule_tenant_resource_quotas'}:
        raise ValueError(
            'Capsule adoption requires one admitted Capsule quota authority before KAORI can take full governance.'
        )

    profile = _materialize_capsule_adoption_profile(tenant, allocation)
    if authority == 'capsule_global_resource_quota':
        from app.kubernetes.tenant.capsule_allocation_governance import (
            cutover_capsule_global_quota_allocation,
        )

        cutover_capsule_global_quota_allocation(
            tenant_id=tenant.id,
            profile_id=profile.id,
        )
    else:
        from app.kubernetes.tenant.capsule_tenant_quota_governance import (
            cutover_capsule_tenant_resource_quota,
        )

        cutover_capsule_tenant_resource_quota(
            tenant_id=tenant.id,
            profile_id=profile.id,
        )
    return profile


def adopt_discovered_tenant_committed(
    source: Mapping[str, Any],
) -> tuple[Tenant, TenantEnvironment, TenantNamespace | None]:
    """Adopt provider state into KAORI and take over supported governance without changing effective values."""

    cluster_id = str(source.get('cluster_id') or '').strip()
    provider_key = str(source.get('provider_key') or '').strip().lower()
    resource_name = str(source.get('resource_name') or '').strip()
    tenant_name = str(source.get('tenant_name') or resource_name).strip()
    environment_name = _adoption_environment(str(source.get('environment') or ''))

    if provider_key not in {'native_kubernetes', 'capsule'}:
        raise ValueError('Unsupported Tenant discovery provider.')
    if not resource_name:
        raise ValueError('Select a discovered provider object.')
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
    from app.kubernetes.tenant.native_provider import tenant_workspace_connection_available

    if cluster is None or not tenant_workspace_connection_available(cluster.kubernetes_connection):
        raise ValueError('The selected Kubernetes cluster is not available for Tenant adoption.')

    client = runtime_adapter.build_client(cluster)
    now = datetime.now(UTC)

    # Import here to reuse the canonical KAORI slug contract without making
    # discovery a provider-specific clone of Tenant creation logic.
    from app.kubernetes.tenant.service import normalize_tenant_slug

    slug = normalize_tenant_slug(str(source.get('tenant_slug') or tenant_name))
    tenant_generation = _next_tenant_generation(cluster_id=str(cluster.id), slug=slug)

    tenant = Tenant()
    tenant.cluster_id = cluster.id
    tenant.name = tenant_name
    tenant.slug = slug
    tenant.generation = tenant_generation
    tenant.description = f'Adopted from live {provider_key.replace("_", " ")} discovery.'
    tenant.lifecycle_status = TenantLifecycleStatus.READY.value
    tenant.ownership_status = TenantOwnershipStatus.ADOPTED.value

    namespace_record: TenantNamespace | None = None

    if provider_key == 'native_kubernetes':
        try:
            item = client.core_api().read_namespace(resource_name, _request_timeout=5)
        except ApiException as exc:
            if exc.status == 404:
                raise ValueError('The discovered namespace is no longer present in Kubernetes.') from exc
            raise

        metadata = getattr(item, 'metadata', None)
        labels = dict(getattr(metadata, 'labels', None) or {})
        provider_status = _namespace_phase(item)
        management_status, reason = _native_management(
            namespace=resource_name,
            labels=labels,
            managed_record=_managed_namespace_map([str(cluster.id)]).get((str(cluster.id), resource_name)),
        )
        if provider_status == 'Terminating':
            raise ValueError('The discovered namespace is terminating and cannot be adopted.')
        if management_status != 'Discovered':
            raise ValueError(reason)

        namespace_generation = _next_namespace_generation(
            cluster_id=str(cluster.id),
            namespace=resource_name,
        )
        provider_uid = str(getattr(metadata, 'uid', None) or resource_name)
        resource_version = str(getattr(metadata, 'resource_version', None) or '')
        allocation = observe_native_namespace_allocation(client.core_api(), resource_name)

        tenant.provider_key = 'native_kubernetes'
        tenant.provider_state = 'native'
        tenant.reconciliation_authority = 'native_kubernetes'
        tenant.provider_reference = resource_name
        tenant.provider_evidence_json = {
            'source': 'tenant_discovery_adoption',
            'provider': 'native_kubernetes',
            'resource_kind': 'Namespace',
            'resource_name': resource_name,
            'provider_uid': provider_uid,
            'resource_version': resource_version,
            'adopted_at': now.isoformat(),
            'allocation_provenance': 'adopted_observed',
            'allocation_control_state': allocation['control_state'],
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }

        db.session.add(tenant)

        environment = TenantEnvironment()
        environment.tenant = tenant
        environment.environment = environment_name
        db.session.add(environment)

        namespace_record = TenantNamespace()
        namespace_record.environment = environment
        namespace_record.cluster_id = cluster.id
        namespace_record.namespace = resource_name
        namespace_record.generation = namespace_generation
        namespace_record.ownership_status = TenantOwnershipStatus.ADOPTED.value
        namespace_record.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
        namespace_record.provisioning_message = (
            'Adopted Baseline · Observed. Existing Kubernetes allocation is read-only until governance cutover.'
            if allocation['control_state'] == 'observed'
            else 'Adopted Baseline · Control Unavailable. Review ambiguous or unsupported allocation evidence.'
        )
        namespace_record.allocation_quota_json = dict(allocation['quota'])
        namespace_record.allocation_limit_defaults_json = dict(allocation['limits'])
        namespace_record.allocation_storage_policy_json = dict(allocation.get('storage_policy') or {})
        namespace_record.allocation_customized = True
        namespace_record.desired_hash = None
        namespace_record.effective_hash = str(allocation['effective_hash'])
        namespace_record.provider_reference = provider_uid
        namespace_record.last_reconciled_at = now
        namespace_record.provisioning_evidence_json = {
            'source': 'tenant_discovery_adoption',
            'provider': 'native_kubernetes',
            'provider_uid': provider_uid,
            'resource_version': resource_version,
            'observed_present': True,
            'adopted_at': now.isoformat(),
            'allocation': allocation,
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }
        db.session.add(namespace_record)
        db.session.flush()

        if allocation['control_state'] != 'observed':
            raise ValueError(
                str(
                    allocation.get('control_reason')
                    or 'Native allocation authority is not safe for managed adoption.'
                )
            )

        from app.kubernetes.tenant.allocation_cutover import reconcile_adopted_native_allocation
        from app.kubernetes.tenant.capacity_governance import enforce_existing_namespace_allocation_preflight
        from app.kubernetes.tenant.service import _materialize_adopted_baseline_profile

        profile = _materialize_adopted_baseline_profile(namespace_record)
        capacity_decision = enforce_existing_namespace_allocation_preflight(
            record=namespace_record,
            profile=profile,
            quota_hard=profile.quota_hard_json or {},
        )
        if str(capacity_decision.decision) != 'allow':
            raise ValueError(
                'Adoption cannot take governance ownership because capacity admission did not allow '
                'the observed provider baseline.'
            )

        reconcile_adopted_native_allocation(
            namespace_record,
            profile=profile,
            resource_profile_version=int(profile.version or 1),
            allocation_customized=True,
            capacity_decision_id=capacity_decision.id,
            quota_hard=dict(profile.quota_hard_json or {}),
            limit_defaults=dict(profile.limit_defaults_json or {}),
            storage_policy=dict(profile.storage_policy_json or {}),
            operation='adoption_takeover',
        )

        tenant_evidence = dict(tenant.provider_evidence_json or {})
        tenant_evidence.update(
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
                    'provider_readback_verified': namespace_record.provisioning_status
                    == TenantNamespaceProvisioningStatus.READY.value,
                    'taken_over_at': datetime.now(UTC).isoformat(),
                },
                'provider_mutation_performed': True,
            }
        )
        tenant.provider_evidence_json = tenant_evidence

    else:
        capsule_version, item = _read_capsule_tenant(client, resource_name)
        status = _capsule_phase(item)
        if status == 'Terminating':
            raise ValueError('The Capsule Tenant is terminating and cannot be adopted.')
        if _managed_capsule_map([str(cluster.id)]).get((str(cluster.id), resource_name)) is not None:
            raise ValueError('This Capsule Tenant is already governed by KAORI.')

        metadata = item.get('metadata') or {}
        provider_uid = str(metadata.get('uid') or resource_name)
        resource_version = str(metadata.get('resourceVersion') or '')
        allocation = observe_capsule_tenant_allocation(
            client,
            tenant_name=resource_name,
            tenant_item=item,
        )
        capsule_provider_state, capsule_capability_evidence = qualify_capsule_tenant_adoption(
            cluster=cluster,
            api_version=capsule_version,
            tenant_name=resource_name,
            resource_version=resource_version or None,
        )
        _apply_capsule_allocation_capability_state(
            allocation,
            provider_state=capsule_provider_state,
            capability_evidence=capsule_capability_evidence,
        )

        tenant.provider_key = 'capsule'
        tenant.provider_state = capsule_provider_state
        tenant.reconciliation_authority = 'capsule'
        tenant.provider_reference = resource_name
        tenant.provider_evidence_json = {
            'source': 'tenant_discovery_adoption',
            'provider': 'capsule',
            'provider_api_version': capsule_version,
            'resource_kind': 'Tenant',
            'resource_name': resource_name,
            'provider_uid': provider_uid,
            'resource_version': resource_version,
            'provider_status': status,
            'adopted_at': now.isoformat(),
            'allocation_baseline': allocation,
            'allocation_provenance': 'adopted_observed',
            'allocation_control_state': allocation['control_state'],
            'capsule': capsule_capability_evidence,
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }

        db.session.add(tenant)

        environment = TenantEnvironment()
        environment.tenant = tenant
        environment.environment = environment_name
        db.session.add(environment)
        db.session.flush()

        adopted_namespaces: list[TenantNamespace] = []
        for correlated in allocation['correlated_namespaces']:
            namespace_name = str(correlated.get('name') or '').strip()
            if not namespace_name:
                continue
            namespace_generation = _next_namespace_generation(
                cluster_id=str(cluster.id),
                namespace=namespace_name,
            )
            namespace_allocation = dict(correlated.get('allocation') or {})
            namespace_record_item = TenantNamespace()
            namespace_record_item.environment = environment
            namespace_record_item.cluster_id = cluster.id
            namespace_record_item.namespace = namespace_name
            namespace_record_item.generation = namespace_generation
            namespace_record_item.ownership_status = TenantOwnershipStatus.ADOPTED.value
            namespace_record_item.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
            namespace_record_item.provisioning_message = (
                'Adopted · Provider Mirrored Policy. Capsule remains authoritative; supported Namespace '
                'Container/PVC policy is committed in KAORI without claiming controller-owned write authority.'
                if allocation['control_state'] == 'observed'
                else 'Adopted Baseline · Control Unavailable. Capsule allocation authority requires review.'
            )
            namespace_record_item.allocation_quota_json = dict(namespace_allocation.get('quota') or {})
            namespace_record_item.allocation_limit_defaults_json = dict(namespace_allocation.get('limits') or {})
            namespace_record_item.allocation_storage_policy_json = dict(
                namespace_allocation.get('storage_policy') or {}
            )
            namespace_record_item.allocation_customized = True
            namespace_record_item.desired_hash = None
            namespace_record_item.effective_hash = (
                str(namespace_allocation.get('effective_hash') or '') or None
            )
            namespace_record_item.provider_reference = str(correlated.get('uid') or namespace_name)
            namespace_record_item.last_reconciled_at = now
            namespace_record_item.provisioning_evidence_json = {
                'source': 'tenant_discovery_adoption',
                'provider': 'capsule',
                'provider_uid': str(correlated.get('uid') or ''),
                'resource_version': str(correlated.get('resource_version') or ''),
                'observed_present': True,
                'adopted_at': now.isoformat(),
                'allocation': namespace_allocation,
                'allocation_authority': allocation['allocation_authority'],
                'allocation_control_state': allocation['control_state'],
                'provider_mutation_performed': False,
                'secret_material_persisted': False,
            }
            db.session.add(namespace_record_item)
            adopted_namespaces.append(namespace_record_item)

        for record in adopted_namespaces:
            observation_value = (record.provisioning_evidence_json or {}).get('allocation')
            observation = dict(observation_value) if isinstance(observation_value, Mapping) else {}
            if observation.get('unsupported_dimensions') or observation.get('ambiguous_dimensions'):
                raise ValueError(
                    f'Namespace/{record.namespace} contains unsupported or ambiguous policy dimensions; '
                    'managed adoption fails closed.'
                )
            if observation.get('limits') or observation.get('storage_policy'):
                policy_profile = _materialize_capsule_namespace_policy_profile(
                    tenant,
                    record,
                    observation,
                )
                record.resource_profile = policy_profile
                record.resource_profile_id = policy_profile.id
                record.resource_profile_version = int(policy_profile.version or 1)
                record.allocation_quota_json = {}
                record.allocation_limit_defaults_json = dict(policy_profile.limit_defaults_json or {})
                record.allocation_storage_policy_json = dict(policy_profile.storage_policy_json or {})
                evidence = dict(record.provisioning_evidence_json or {})
                evidence.update(
                    {
                        'allocation_control_state': 'provider_mirrored_policy',
                        'provider_policy_mirror': {
                            'profile_id': policy_profile.public_id,
                            'profile_version': int(policy_profile.version or 1),
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

        shared_profile = _take_over_capsule_allocation(
            tenant=tenant,
            allocation=allocation,
        )
        tenant_evidence = dict(tenant.provider_evidence_json or {})
        tenant_evidence.update(
            {
                'allocation_control_state': 'kaori_managed',
                'adoption_takeover': {
                    'profile_id': shared_profile.public_id if shared_profile is not None else None,
                    'profile_version': int(shared_profile.version or 1) if shared_profile is not None else None,
                    'provider_value_change_requested': False,
                    'effective_values_preserved': True,
                    'namespaced_policy_profiles': [
                        record.resource_profile.public_id
                        for record in adopted_namespaces
                        if record.resource_profile is not None
                    ],
                    'provider_mutation_performed': True,
                    'taken_over_at': datetime.now(UTC).isoformat(),
                },
                'provider_mutation_performed': True,
            }
        )
        tenant.provider_evidence_json = tenant_evidence
        namespace_record = adopted_namespaces[0] if adopted_namespaces else None

    try:
        db.session.commit()
        return tenant, environment, namespace_record
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Tenant adoption conflicted with committed KAORI state. Refresh Discovery and retry.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise
