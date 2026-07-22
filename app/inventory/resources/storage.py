from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_

from app.extensions import db
from app.models import (
    Cluster, ConfigurationInventory, IngressInventory, NamespaceInventory,
    NodeInventory, PodInventory, ResourceQuotaInventory, ServiceInventory,
    StorageInventory, WorkloadInventory,
)

from app.inventory.resources.common import (
    _display_boolean, _pod_summary, _selector_matches, _service_port_rows,
    _split_inventory_values, format_age,
)
from app.inventory.formatting import (
    convert_ki_to_gib, convert_storage_to_gib, format_byte_count,
    format_kubernetes_size, format_quota_value,
)

def _storage_bound_pods(
    item: StorageInventory,
) -> tuple[list[PodInventory], list[dict[str, str]]]:
    details = item.details or {}
    claims: list[dict[str, str]] = []

    if item.storage_type == 'PersistentVolumeClaim' and item.namespace:
        claims.append({'namespace': item.namespace, 'name': item.name})

    elif item.storage_type == 'PersistentVolume':
        claim_namespace = details.get('claim_namespace')
        claim_name = details.get('claim_name')
        if claim_namespace and claim_name:
            claims.append({'namespace': claim_namespace, 'name': claim_name})

    elif item.storage_type == 'StorageClass':
        pvc_rows = (
            StorageInventory.query.filter_by(
                cluster_id=item.cluster_id,
                storage_type='PersistentVolumeClaim',
                storage_class=item.name,
            )
            .order_by(StorageInventory.namespace, StorageInventory.name)
            .all()
        )
        claims.extend(
            {
                'namespace': pvc.namespace or '-',
                'name': pvc.name,
            }
            for pvc in pvc_rows
            if pvc.namespace
        )

    if not claims:
        return [], []

    claim_lookup = {(claim['namespace'], claim['name']) for claim in claims}
    pods = (
        PodInventory.query.filter_by(cluster_id=item.cluster_id)
        .order_by(
            PodInventory.namespace,
            PodInventory.pod_name,
        )
        .all()
    )

    matched = [
        pod
        for pod in pods
        if any((pod.namespace, claim_name) in claim_lookup for claim_name in (pod.persistent_volume_claims or []))
    ]

    return matched, claims


def get_storage_detail(storage_id: int) -> dict[str, Any] | None:
    result = (
        db.session.query(
            StorageInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == StorageInventory.cluster_id)
        .filter(StorageInventory.id == storage_id)
        .first()
    )

    if result is None:
        return None

    item, cluster_name = result
    namespace = item.namespace
    if item.storage_type in {'StorageClass', 'PersistentVolume'}:
        namespace = 'Cluster-wide'

    bound_pods, claims = _storage_bound_pods(item)
    details = dict(item.details or {})
    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}
    source = details.get('source') or {}

    requested_storage = details.get('requested_storage')
    if requested_storage:
        requested_storage = format_kubernetes_size(requested_storage)

    if item.storage_type == 'PersistentVolume':
        binding_reference = (
            f'{details.get("claim_namespace")}/{details.get("claim_name")}'
            if details.get('claim_namespace') and details.get('claim_name')
            else 'Unbound'
        )
    elif item.storage_type == 'PersistentVolumeClaim':
        binding_reference = details.get('volume_name') or 'Unbound'
    else:
        binding_reference = f'{len(claims)} claim(s)'

    return {
        'id': item.id,
        'cluster_name': cluster_name,
        'namespace': namespace or '-',
        'name': item.name,
        'type': item.storage_type,
        'type_description': STORAGE_TYPE_DESCRIPTIONS.get(
            item.storage_type,
            'Kubernetes storage metadata from the latest inventory snapshot.',
        ),
        'storage_class': item.storage_class or '-',
        'capacity': format_kubernetes_size(item.capacity),
        'requested_storage': requested_storage or '-',
        'status': item.status or 'Unknown',
        'details': details,
        'uid': details.get('uid') or '-',
        'finalizers': details.get('finalizers') or [],
        'access_modes': details.get('access_modes') or [],
        'volume_mode': details.get('volume_mode') or '-',
        'reclaim_policy': details.get('reclaim_policy') or '-',
        'binding_mode': details.get('volume_binding_mode') or '-',
        'allow_expansion': bool(details.get('allow_volume_expansion')),
        'provisioner': details.get('provisioner') or '-',
        'parameters': sorted((details.get('parameters') or {}).items()),
        'mount_options': details.get('mount_options') or [],
        'allowed_topology_count': int(details.get('allowed_topology_count') or 0),
        'is_default': bool(details.get('is_default')),
        'node_affinity_configured': bool(details.get('node_affinity_configured')),
        'source': source,
        'selector': sorted((details.get('selector') or {}).items()),
        'data_source': details.get('data_source'),
        'conditions': details.get('conditions') or [],
        'binding_reference': binding_reference,
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'claim_count': len(claims),
        'claims': claims[:8],
        'claims_truncated': len(claims) > 8,
        'pod_count': len(bound_pods),
        'pods': [_pod_summary(pod) for pod in bound_pods[:8]],
        'pods_truncated': len(bound_pods) > 8,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
        'details_reported': bool(details),
    }


def get_storage_filter_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(StorageInventory.storage_type)
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    rows = query.distinct().order_by(StorageInventory.storage_type).all()
    return [row[0] for row in rows if row[0]]


def get_storage_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
    storage_type: str | None = None,
) -> list[str]:
    query = db.session.query(StorageInventory.status)
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    if storage_type:
        query = query.filter(StorageInventory.storage_type == storage_type)
    rows = query.distinct().order_by(StorageInventory.status).all()
    return [row[0] for row in rows if row[0]]


def get_storage_inventory_view(
    cluster_id=None,
    namespace=None,
    storage_type=None,
    status=None,
    search=None,
):
    query = db.session.query(
        StorageInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == StorageInventory.cluster_id)

    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    if storage_type:
        query = query.filter(StorageInventory.storage_type == storage_type)
    if status:
        query = query.filter(StorageInventory.status == status)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                StorageInventory.name.ilike(pattern),
                StorageInventory.storage_class.ilike(pattern),
                StorageInventory.status.ilike(pattern),
            )
        )

    items = query.order_by(
        Cluster.name,
        StorageInventory.storage_type,
        StorageInventory.name,
    ).all()

    namespace_query = db.session.query(StorageInventory.namespace).distinct()
    if cluster_id:
        namespace_query = namespace_query.filter(StorageInventory.cluster_id == cluster_id)
    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    data: list[dict[str, Any]] = []
    storage_classes = 0
    persistent_volumes = 0
    persistent_volume_claims = 0
    storage_types: dict[str, int] = {
        'StorageClass': 0,
        'PersistentVolume': 0,
        'PersistentVolumeClaim': 0,
    }

    for item, cluster_name in items:
        if item.storage_type in storage_types:
            storage_types[item.storage_type] += 1
        if item.storage_type == 'StorageClass':
            storage_classes += 1
        elif item.storage_type == 'PersistentVolume':
            persistent_volumes += 1
        elif item.storage_type == 'PersistentVolumeClaim':
            persistent_volume_claims += 1

        namespace_display = item.namespace
        if item.storage_type in {'StorageClass', 'PersistentVolume'}:
            namespace_display = 'Cluster-wide'
        elif not namespace_display:
            namespace_display = '-'

        details = item.details or {}
        if item.storage_type == 'PersistentVolume':
            binding = (
                f'{details.get("claim_namespace")}/{details.get("claim_name")}'
                if details.get('claim_namespace') and details.get('claim_name')
                else 'Unbound'
            )
        elif item.storage_type == 'PersistentVolumeClaim':
            binding = details.get('volume_name') or 'Unbound'
        else:
            binding = details.get('provisioner') or '-'

        capacity = item.capacity
        if item.storage_type == 'PersistentVolumeClaim' and details.get('requested_storage'):
            capacity = details.get('requested_storage')

        data.append(
            {
                'id': item.id,
                'cluster_name': cluster_name,
                'namespace': namespace_display,
                'name': item.name,
                'type': item.storage_type,
                'storage_class': item.storage_class or '-',
                'capacity': format_kubernetes_size(capacity),
                'status': item.status or 'Unknown',
                'binding': binding,
                'is_default': bool(details.get('is_default')),
                'created_at': item.created_at,
                'collected_at': item.collected_at,
            }
        )

    return {
        'total_storage': len(items),
        'storage_classes': storage_classes,
        'persistent_volumes': persistent_volumes,
        'persistent_volume_claims': persistent_volume_claims,
        'namespaces': namespaces,
        'storage_filter_types': get_storage_filter_types(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'storage_filter_statuses': get_storage_filter_statuses(
            cluster_id=cluster_id,
            namespace=namespace,
            storage_type=storage_type,
        ),
        'storage_types': storage_types,
        'storage_items': data,
    }


