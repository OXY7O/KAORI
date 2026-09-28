from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kubernetes.client.rest import ApiException

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.models import Cluster
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import Tenant, TenantEnvironment, TenantNamespace

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
    return 'Adoptable', 'Eligible for governed adoption preflight; no provider mutation has occurred.'


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
            management_status, eligibility = _native_management(
                namespace=name,
                labels=labels,
                managed_record=managed_record,
            )
            tenant = managed_record.environment.tenant if managed_record is not None else None
            rows.append({
                'cluster': cluster,
                'cluster_id': cluster_key,
                'provider_key': 'native_kubernetes',
                'provider_label': 'Native Kubernetes',
                'resource_kind': 'Namespace',
                'resource_name': name,
                'provider_status': _namespace_phase(item),
                'provider_tone': _tone(_namespace_phase(item)),
                'management_status': management_status,
                'management_tone': 'normal' if management_status == 'Managed' else ('info' if management_status == 'Adoptable' else 'warning'),
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
            management_status = 'Managed' if tenant is not None else 'Adoptable'
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
                'management_tone': 'normal' if management_status == 'Managed' else 'info',
                'tenant_name': tenant.name if tenant is not None else None,
                'tenant_id': tenant.id if tenant is not None else None,
                'eligibility': (
                    'Already governed by KAORI.'
                    if tenant is not None
                    else 'Eligible for governed Capsule adoption preflight; provider authority remains Capsule.'
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
            0 if row['management_status'] == 'Adoptable' else 1,
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
