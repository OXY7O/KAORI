from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.models import Cluster
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
            namespace_items = client.core_api().list_namespace(_request_timeout=5).items or []
        except Exception:
            errors.append({
                'cluster_id': cluster_key,
                'cluster_name': cluster.name,
                'message': 'Live Kubernetes namespace discovery failed.',
            })
            continue

        for item in namespace_items:
            metadata = getattr(item, 'metadata', None)
            name = str(getattr(metadata, 'name', None) or '').strip()
            if not name:
                continue
            labels = dict(getattr(metadata, 'labels', None) or {})
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
            rows.append({
                'cluster': cluster,
                'cluster_id': cluster_key,
                'provider_key': 'native_kubernetes',
                'provider_label': 'Native Kubernetes',
                'resource_kind': 'Namespace',
                'resource_name': name,
                'provider_status': provider_status,
                'provider_tone': _tone(provider_status),
                'management_status': management_status,
                'management_tone': 'normal' if management_status == 'Managed' else ('info' if management_status == 'Discovered' else 'warning'),
                'tenant_name': tenant.name if tenant is not None else None,
                'tenant_id': tenant.id if tenant is not None else None,
                'eligibility': eligibility,
                'provider_reference': str(getattr(metadata, 'uid', None) or name),
            })

        try:
            capsule_version, capsule_items = _capsule_items(client)
        except Exception:
            errors.append({
                'cluster_id': cluster_key,
                'cluster_name': cluster.name,
                'message': 'Live Capsule Tenant discovery failed.',
            })
            capsule_version, capsule_items = None, []

        for item in capsule_items:
            metadata = item.get('metadata') or {}
            name = str(metadata.get('name') or '').strip()
            if not name:
                continue
            tenant = managed_capsule.get((cluster_key, name))
            status = _capsule_phase(item)
            management_status = 'Managed' if tenant is not None else ('Blocked' if status == 'Terminating' else 'Discovered')
            rows.append({
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
                    'normal' if management_status == 'Managed'
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
            })

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
    if any(
        item.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
        for item in prior
    ):
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


def adopt_discovered_tenant_committed(source: Mapping[str, Any]) -> tuple[Tenant, TenantEnvironment, TenantNamespace | None]:
    """Adopt an existing provider object without mutating Kubernetes or Capsule."""

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
        .filter(Cluster.id == cluster_id)
        .first()
    )
    if cluster is None:
        raise ValueError('The selected Kubernetes cluster is no longer available for Tenant adoption.')

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
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }

        db.session.add(tenant)
        db.session.flush()

        environment = TenantEnvironment()
        environment.tenant_id = tenant.id
        environment.environment = environment_name
        db.session.add(environment)
        db.session.flush()

        namespace_record = TenantNamespace()
        namespace_record.tenant_environment_id = environment.id
        namespace_record.cluster_id = cluster.id
        namespace_record.namespace = resource_name
        namespace_record.generation = namespace_generation
        namespace_record.ownership_status = TenantOwnershipStatus.ADOPTED.value
        namespace_record.provisioning_status = TenantNamespaceProvisioningStatus.READY.value
        namespace_record.provisioning_message = 'Existing Kubernetes namespace adopted without provider mutation.'
        namespace_record.provider_reference = provider_uid
        namespace_record.last_reconciled_at = now
        namespace_record.provisioning_evidence_json = {
            'source': 'tenant_discovery_adoption',
            'provider': 'native_kubernetes',
            'provider_uid': provider_uid,
            'resource_version': resource_version,
            'observed_present': True,
            'adopted_at': now.isoformat(),
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }
        db.session.add(namespace_record)

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

        tenant.provider_key = 'capsule'
        tenant.provider_state = 'capsule'
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
            'provider_mutation_performed': False,
            'secret_material_persisted': False,
        }

        db.session.add(tenant)
        db.session.flush()

        environment = TenantEnvironment()
        environment.tenant_id = tenant.id
        environment.environment = environment_name
        db.session.add(environment)

    try:
        db.session.commit()
        return tenant, environment, namespace_record
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Tenant adoption conflicted with committed KAORI state. Refresh Discovery and retry.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise
