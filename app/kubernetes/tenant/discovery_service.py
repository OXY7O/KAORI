from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from kubernetes.client.rest import ApiException

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.allocation_observation import observe_native_namespace_allocation
from app.kubernetes.tenant.capsule_allocation_observation import (
    _capsule_namespace_correlation,
    _capsule_status_namespace_names,
    observe_capsule_tenant_allocation,
)
from app.kubernetes.tenant.capsule_namespace_attachment_authority import (
    validate_capsule_namespace_attachment,
)
from app.kubernetes.tenant.capsule_provider import discover_capsule
from app.models import Cluster
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantEnvironmentName,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
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
    # A partial or orphaned KAORI allocation label is still ownership
    # evidence; absence of a tenant-id does not make a takeover safe.
    reserved_claims = ('kaori.io/tenant-id', 'kaori.io/environment', 'kaori.io/resource-profile')
    if external_manager.lower() == 'kaori' or any(key in labels for key in reserved_claims):
        return (
            'Blocked',
            'Namespace has KAORI ownership markers without active governance; '
            'inspect provider residue and recover the prior Tenant before adoption.',
        )
    if external_manager:
        return 'Blocked', f'Provider resource declares external manager {external_manager}.'
    return 'Discovered', 'Candidate for governed adoption preflight; no provider mutation has occurred.'


def _managed_namespace_map(cluster_ids: list[str]) -> dict[tuple[str, str], TenantNamespace]:
    if not cluster_ids:
        return {}
    rows = (
        TenantNamespace.query.filter(
            TenantNamespace.cluster_id.in_(cluster_ids),
            TenantNamespace.provisioning_status.notin_(('deprovisioned', 'released')),
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
        Tenant.lifecycle_status.notin_(('decommissioned', 'released')),
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

        # Surface only ungoverned Capsule Namespaces correlated to an already
        # governed Capsule Tenant; never require operators to recreate the Tenant.
        namespace_by_name = {
            str(getattr(getattr(item, 'metadata', None), 'name', '') or ''): item
            for item in namespace_items
        }
        for capsule_item in capsule_items:
            capsule_metadata = capsule_item.get('metadata') or {}
            capsule_name = str(capsule_metadata.get('name') or '').strip()
            capsule_tenant = managed_capsule.get((cluster_key, capsule_name))
            if (
                capsule_tenant is None
                or capsule_tenant.provider_state != 'capsule'
                or capsule_tenant.reconciliation_authority != 'capsule'
                or capsule_tenant.lifecycle_status != 'ready'
                or _capsule_phase(capsule_item) == 'Terminating'
            ):
                continue
            correlated, ambiguities = _capsule_namespace_correlation(
                core_api=client.core_api(),
                tenant_name=capsule_name,
                tenant_item=capsule_item,
                namespace_items=namespace_items,
            )
            capsule_uid = str(capsule_metadata.get('uid') or '').strip()
            expected_uid = str((capsule_tenant.provider_evidence_json or {}).get('provider_uid') or '')
            if not capsule_uid or capsule_uid != expected_uid:
                ambiguities.append('Capsule Tenant CR UID changed since KAORI adoption.')
            for observed in correlated[:30]:
                name = str(observed.get('name') or '')
                if not name or managed_namespaces.get((cluster_key, name)) is not None:
                    continue
                obj = namespace_by_name.get(name)
                if obj is None:
                    continue
                namespace_status = _namespace_phase(obj)
                label_claims = set(observed.get('label_claims') or [])
                owner_claims = set(observed.get('owner_claims') or [])
                correlation_proven = bool(
                    (label_claims or owner_claims)
                    and (not label_claims or label_claims == {capsule_name})
                    and (not owner_claims or owner_claims == {capsule_name})
                )
                authority_error = ''
                try:
                    validate_capsule_namespace_attachment(
                        tenant=capsule_tenant, cluster_id=cluster_key,
                        capsule_item=capsule_item, namespace=obj,
                        expected_namespace_uid=str(observed.get('uid') or ''),
                        status_namespace_names=_capsule_status_namespace_names(capsule_item),
                    )
                except ValueError as exc:
                    authority_error = str(exc)
                blocked = bool(
                    authority_error or ambiguities or not correlation_proven
                    or namespace_status == 'Terminating'
                    or not observed.get('uid') or not observed.get('resource_version')
                )
                eligibility = (
                    authority_error if authority_error else
                    '; '.join(ambiguities[:3]) if ambiguities else
                    'Capsule Namespace is terminating.' if namespace_status == 'Terminating' else
                    'Explicit Capsule label/owner-ref correlation is missing.' if not correlation_proven else
                    'Provider Namespace UID/resourceVersion is incomplete.' if blocked else
                    'Attach this Capsule-correlated Namespace to its existing KAORI Tenant.'
                )
                rows.append({
                    'cluster': cluster, 'cluster_id': cluster_key,
                    'provider_key': 'capsule', 'provider_label': 'Capsule',
                    'resource_kind': 'Capsule Namespace',
                    'resource_name': name,
                    'capsule_tenant_name': capsule_name,
                    'provider_status': namespace_status,
                    'provider_tone': _tone(namespace_status),
                    'management_status': 'Blocked' if blocked else 'Discovered',
                    'management_tone': 'warning' if blocked else 'info',
                    'tenant_name': capsule_tenant.name, 'tenant_id': capsule_tenant.id,
                    'eligibility': eligibility,
                    'provider_reference': str(observed['uid']),
                    'provider_resource_version': str(observed['resource_version']),
                })

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
    capsule_tenant_name: str = '',
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
    if normalized_provider == 'capsule' and capsule_tenant_name:
        return _capsule_namespace_attachment_preflight(
            cluster=cluster, client=client, cluster_id=normalized_cluster,
            namespace=normalized_resource, capsule_tenant_name=capsule_tenant_name,
        )

    if normalized_provider == 'native_kubernetes':
        try:
            item = client.core_api().read_namespace(normalized_resource, _request_timeout=5)
        except ApiException as exc:
            if exc.status == 404:
                raise ValueError('The discovered namespace is no longer present in Kubernetes.') from exc
            raise

        metadata = getattr(item, 'metadata', None)
        labels = dict(getattr(metadata, 'labels', None) or {})
        managed_record = _managed_namespace_map([normalized_cluster]).get((normalized_cluster, normalized_resource))
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
        if not getattr(metadata, 'uid', None) or not getattr(metadata, 'resource_version', None):
            raise ValueError('Native Namespace preflight has no immutable UID/resourceVersion evidence.')

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
            'provider_reference': str(metadata.uid),
            'provider_resource_version': str(metadata.resource_version),
            'allocation_preflight': allocation,
        }
    else:
        capsule_version, item = _read_capsule_tenant(client, normalized_resource)
        tenant = _managed_capsule_map([normalized_cluster]).get((normalized_cluster, normalized_resource))
        provider_status = _capsule_phase(item)
        management_status = (
            'Managed' if tenant is not None else ('Blocked' if provider_status == 'Terminating' else 'Discovered')
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
        provider_meta = item.get('metadata') or {}
        if not provider_meta.get('uid') or not provider_meta.get('resourceVersion'):
            raise ValueError('Capsule Tenant preflight has no immutable UID/resourceVersion evidence.')

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
            'provider_reference': str(metadata['uid']),
            'provider_resource_version': str(metadata['resourceVersion']),
            'provider_api_version': capsule_version,
            'allocation_preflight': allocation,
            'capsule_capability_preflight': capsule_capability_evidence,
        }

    existing_tenant_environments: list[dict[str, Any]] = []
    if normalized_provider == 'native_kubernetes':
        candidates = (
            TenantEnvironment.query.join(Tenant, TenantEnvironment.tenant_id == Tenant.id)
            .filter(
                Tenant.cluster_id == normalized_cluster,
                Tenant.provider_key == 'native_kubernetes',
                Tenant.provider_state == 'native',
                Tenant.reconciliation_authority == 'native_kubernetes',
                Tenant.lifecycle_status == 'ready',
            )
            .order_by(Tenant.name.asc(), TenantEnvironment.environment.asc())
            .all()
        )
        existing_tenant_environments = [
            {
                'id': environment.id,
                'tenant_id': environment.tenant_id,
                'tenant_name': environment.tenant.name,
                'environment': environment.environment,
            }
            for environment in candidates
        ]

    return {
        'tenant_adoption_row': row,
        'tenant_adoption_existing_environments': existing_tenant_environments,
        'tenant_adoption_checked_at': present_user_datetime(datetime.now(UTC)),
    }


def select_capsule_namespace_attachment_candidate(
    allocation: Mapping[str, Any],
    *,
    namespace: str,
    capsule_tenant_name: str,
    expected_uid: str = '',
    expected_resource_version: str = '',
) -> dict[str, Any]:
    """Single fail-closed provider correlation contract for preview and submit."""
    if (
        allocation.get('authority_unsupported_dimensions')
        or allocation.get('authority_ambiguous_dimensions')
        or allocation.get('ambiguous_dimensions')
    ):
        raise ValueError('Capsule authority or Namespace correlation is ambiguous.')
    matches = [
        item for item in allocation.get('correlated_namespaces') or []
        if item.get('name') == namespace
    ]
    if len(matches) != 1:
        raise ValueError('Namespace is not uniquely correlated to its Capsule Tenant.')
    candidate = dict(matches[0])
    label_claims = set(candidate.get('label_claims') or [])
    owner_claims = set(candidate.get('owner_claims') or [])
    if (
        not capsule_tenant_name
        or (not label_claims and not owner_claims)
        or (label_claims and label_claims != {capsule_tenant_name})
        or (owner_claims and owner_claims != {capsule_tenant_name})
    ):
        raise ValueError('Capsule Namespace must have an unambiguous Tenant label or owner reference.')
    uid = str(candidate.get('uid') or '')
    version = str(candidate.get('resource_version') or '')
    if not uid or not version:
        raise ValueError('Capsule Namespace identity evidence is incomplete.')
    if expected_uid and uid != expected_uid:
        raise ValueError('Namespace UID changed since Capsule Adoption Preflight.')
    if expected_resource_version and version != expected_resource_version:
        raise ValueError('Namespace resourceVersion changed since Capsule Adoption Preflight.')
    observed = candidate.get('allocation') or {}
    if (
        observed.get('control_state') != 'observed'
        or observed.get('unsupported_dimensions')
        or observed.get('ambiguous_dimensions')
    ):
        raise ValueError('Capsule Namespace allocation is unsupported or ambiguous.')
    return candidate


def _capsule_namespace_attachment_preflight(
    *, cluster: Cluster, client: Any, cluster_id: str,
    namespace: str, capsule_tenant_name: str,
) -> dict[str, Any]:
    """Read-only, provider-correlated Capsule Namespace attachment preview."""
    tenant = _managed_capsule_map([cluster_id]).get((cluster_id, capsule_tenant_name))
    if (
        tenant is None or tenant.lifecycle_status != 'ready'
        or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or str(tenant.provider_reference or '') != capsule_tenant_name
    ):
        raise ValueError('No healthy governed Capsule Tenant matches the selected Namespace.')
    if _managed_namespace_map([cluster_id]).get((cluster_id, namespace)) is not None:
        raise ValueError('Namespace is already governed by KAORI.')

    capsule_version, item = _read_capsule_tenant(client, capsule_tenant_name)
    metadata = item.get('metadata') or {}
    if (
        not metadata.get('uid')
        or metadata.get('uid') != (tenant.provider_evidence_json or {}).get('provider_uid')
        or _capsule_phase(item) == 'Terminating'
    ):
        raise ValueError('Capsule Tenant identity is stale or terminating.')
    allocation = observe_capsule_tenant_allocation(
        client, tenant_name=capsule_tenant_name, tenant_item=item,
    )
    correlated = select_capsule_namespace_attachment_candidate(
        allocation, namespace=namespace, capsule_tenant_name=capsule_tenant_name,
    )
    observed = client.core_api().read_namespace(namespace, _request_timeout=5)
    provider_status = _namespace_phase(observed)
    proof = validate_capsule_namespace_attachment(
        tenant=tenant, cluster_id=cluster_id, capsule_item=item,
        namespace=observed, expected_namespace_uid=str(correlated['uid']),
        status_namespace_names=_capsule_status_namespace_names(item),
    )
    if proof['namespace_resource_version'] != str(correlated['resource_version']):
        raise ValueError('Capsule Namespace changed since Discovery; review provider authority again.')
    meta = getattr(observed, 'metadata', None)
    if (
        provider_status == 'Terminating'
        or not correlated.get('uid')
        or correlated['uid'] != str(getattr(meta, 'uid', '') or '')
        or str(correlated.get('resource_version') or '') != str(getattr(meta, 'resource_version', '') or '')
    ):
        raise ValueError('Capsule Namespace is terminating or provider identity changed.')
    environments = (
        TenantEnvironment.query.filter_by(tenant_id=tenant.id)
        .order_by(TenantEnvironment.environment.asc()).all()
    )
    if not environments:
        raise ValueError('The governed Capsule Tenant has no destination environment.')
    return {
        'tenant_adoption_row': {
            'cluster': cluster, 'cluster_id': cluster_id,
            'provider_key': 'capsule', 'provider_label': 'Capsule',
            'resource_kind': 'Capsule Namespace', 'resource_name': namespace,
            'capsule_tenant_name': capsule_tenant_name,
            'provider_status': provider_status, 'provider_tone': _tone(provider_status),
            'management_status': 'Discovered', 'management_tone': 'info',
            'tenant_name': tenant.name, 'tenant_id': tenant.id,
            'eligibility': 'Provider-correlated Namespace can attach to the existing Capsule Tenant.',
            'provider_reference': str(correlated['uid']),
            'provider_resource_version': str(correlated['resource_version']),
            'provider_api_version': capsule_version,
            'allocation_preflight': {**allocation, 'correlated_namespaces': [correlated]},
        },
        'tenant_adoption_existing_environments': [
            {
                'id': env.id, 'tenant_id': tenant.id, 'tenant_name': tenant.name,
                'environment': env.environment,
            } for env in environments
        ],
        'tenant_adoption_attachment_only': True,
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
    terminal = {TenantLifecycleStatus.DECOMMISSIONED.value, TenantLifecycleStatus.RELEASED.value}
    if any(item.lifecycle_status not in terminal for item in prior):
        raise ValueError('An active KAORI Tenant with this name/slug already exists on the selected cluster.')
    return max((int(item.generation or 1) for item in prior), default=0) + 1


def _next_namespace_generation(*, cluster_id: str, namespace: str) -> int:
    prior = (
        TenantNamespace.query.filter_by(cluster_id=cluster_id, namespace=namespace)
        .order_by(TenantNamespace.generation.desc(), TenantNamespace.created_at.desc())
        .all()
    )
    terminal = {TenantNamespaceProvisioningStatus.DEPROVISIONED.value, TenantNamespaceProvisioningStatus.RELEASED.value}
    if any(item.provisioning_status not in terminal for item in prior):
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
