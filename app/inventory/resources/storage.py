from __future__ import annotations

from typing import Any

from sqlalchemy import and_, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.formatting import format_kubernetes_size
from app.inventory.resources.common import format_age
from app.inventory.resources.descriptions import STORAGE_TYPE_DESCRIPTIONS
from app.models import Cluster, PodInventory, StorageInventory


_STORAGE_TYPE_LABELS = {
    'StorageClass': 'StorageClass',
    'PersistentVolume': 'PersistentVolume',
    'PersistentVolumeClaim': 'PersistentVolumeClaim',
}


def _storage_lifecycle(storage_type: str, status: str | None) -> tuple[str, str]:
    value = status or 'Unknown'
    if storage_type == 'StorageClass':
        return 'Configured', 'normal'
    if value == 'Bound':
        return 'Bound', 'normal'
    if value == 'Available':
        return 'Available', 'info'
    if value == 'Pending':
        return 'Pending', 'warning'
    if value == 'Released':
        return 'Released', 'warning'
    if value in {'Failed', 'Lost'}:
        return value, 'critical'
    return value, 'unknown'


def _pod_state(pod: PodInventory) -> tuple[str, str, str]:
    phase = pod.phase or 'Unknown'
    ready = pod.ready or '-'
    if phase == 'Succeeded':
        return 'Completed', 'info', f'{phase} · {ready} Ready'
    if phase == 'Failed':
        return 'Failed', 'critical', f'{phase} · {ready} Ready'
    if phase == 'Pending':
        return 'Starting', 'pending', f'{phase} · {ready} Ready'
    if phase == 'Running':
        if ready and '/' in ready and ready.split('/', 1)[0] == ready.split('/', 1)[1]:
            return 'Ready', 'normal', f'{phase} · {ready} Ready'
        return 'Not Ready', 'warning', f'{phase} · {ready} Ready'
    return 'Unknown', 'unknown', f'{phase} · {ready} Ready'


def _claim_rows(item: StorageInventory) -> list[tuple[str, str]]:
    details = item.details or {}
    if item.storage_type == 'PersistentVolumeClaim' and item.namespace:
        return [(item.namespace, item.name)]
    if item.storage_type == 'PersistentVolume':
        namespace = details.get('claim_namespace')
        name = details.get('claim_name')
        return [(str(namespace), str(name))] if namespace and name else []
    if item.storage_type == 'StorageClass':
        query = filter_current_generation(
            db.session.query(StorageInventory.namespace, StorageInventory.name),
            StorageInventory,
        ).filter(
            StorageInventory.cluster_id == item.cluster_id,
            StorageInventory.storage_type == 'PersistentVolumeClaim',
            StorageInventory.storage_class == item.name,
            StorageInventory.namespace.is_not(None),
        )
        return [(str(namespace), str(name)) for namespace, name in query.order_by(StorageInventory.namespace, StorageInventory.name).all()]
    return []


def _related_storage_resources(item: StorageInventory) -> tuple[list[dict[str, Any]], int, bool, list[dict[str, Any]], int, bool]:
    claims = _claim_rows(item)
    claim_resources: list[dict[str, Any]] = []
    for namespace, name in claims[:8]:
        claim_resources.append(
            {
                'name': name,
                'supporting_primary': f'Namespace · {namespace}',
                'supporting_secondary': 'PersistentVolumeClaim reference',
                'status': None,
                'status_tone': None,
            }
        )

    if not claims:
        return claim_resources, 0, False, [], 0, False

    pod_base_query = filter_current_generation(PodInventory.query, PodInventory).filter(
        PodInventory.cluster_id == item.cluster_id,
    )
    try:
        dialect = db.session.get_bind().dialect.name
    except Exception:
        dialect = ''

    if dialect == 'postgresql':
        clauses = [
            and_(
                PodInventory.namespace == namespace,
                cast(PodInventory.persistent_volume_claims, JSONB).contains([name]),
            )
            for namespace, name in claims[:200]
        ]
        pod_query = pod_base_query.filter(or_(*clauses))
        pod_count = pod_query.count()
        pod_rows = pod_query.order_by(PodInventory.namespace, PodInventory.pod_name).limit(8).all()
    else:
        claim_names_by_namespace: dict[str, set[str]] = {}
        for namespace, name in claims[:200]:
            claim_names_by_namespace.setdefault(namespace, set()).add(name)
        candidate_rows = pod_base_query.filter(
            PodInventory.namespace.in_(sorted(claim_names_by_namespace))
        ).order_by(PodInventory.namespace, PodInventory.pod_name).all()
        matched_rows = [
            pod
            for pod in candidate_rows
            if claim_names_by_namespace.get(pod.namespace, set()).intersection(
                set(pod.persistent_volume_claims or [])
            )
        ]
        pod_count = len(matched_rows)
        pod_rows = matched_rows[:8]
    pod_resources = []
    for pod in pod_rows:
        state, tone, evidence = _pod_state(pod)
        pod_resources.append(
            {
                'name': pod.pod_name,
                'supporting_primary': f'Namespace · {pod.namespace} · Node {pod.node_name or "Not Assigned"}',
                'supporting_secondary': evidence,
                'status': state,
                'status_tone': tone,
            }
        )
    return claim_resources, len(claims), len(claims) > 8, pod_resources, pod_count, pod_count > 8


def _storage_operational_context(item: StorageInventory, lifecycle_label: str) -> dict[str, str]:
    if item.storage_type == 'PersistentVolumeClaim' and lifecycle_label == 'Pending':
        return {
            'title': 'Review Claim Binding',
            'description': 'Confirm StorageClass selection, provisioner availability, topology constraints, and pending volume events.',
            'tone': 'warning',
            'icon': 'link-2-off',
        }
    if item.storage_type == 'PersistentVolume' and lifecycle_label == 'Released':
        return {
            'title': 'Review Reclaim Lifecycle',
            'description': 'Confirm whether the released volume should be retained, recycled externally, or prepared for a new claim.',
            'tone': 'warning',
            'icon': 'archive-restore',
        }
    if lifecycle_label in {'Lost', 'Failed'}:
        return {
            'title': 'Investigate Storage Failure',
            'description': 'Review binding evidence, provisioner events, volume source state, and the owning application before relying on this storage object.',
            'tone': 'critical',
            'icon': 'circle-x',
        }
    if item.storage_type == 'PersistentVolume' and lifecycle_label == 'Available':
        return {
            'title': 'Volume Available for Binding',
            'description': 'The committed snapshot reports unbound capacity. Confirm access modes, StorageClass, and topology before claim binding.',
            'tone': 'info',
            'icon': 'hard-drive-download',
        }
    if item.storage_type == 'StorageClass':
        return {
            'title': 'Provisioning Class Ready for Review',
            'description': 'Review provisioner, binding mode, expansion capability, reclaim policy, and topology configuration as factual evidence.',
            'tone': 'info',
            'icon': 'layers-3',
        }
    return {
        'title': 'Storage Binding Snapshot Ready for Review',
        'description': 'No exceptional lifecycle state is represented in the latest committed storage snapshot.',
        'tone': 'normal',
        'icon': 'circle-check',
    }


def get_storage_detail(storage_id: int) -> dict[str, Any] | None:
    query = db.session.query(StorageInventory, Cluster.name.label('cluster_name')).join(
        Cluster, Cluster.id == StorageInventory.cluster_id
    )
    query = filter_current_generation(query, StorageInventory)
    result = query.filter(StorageInventory.id == storage_id).first()
    if result is None:
        return None

    item, cluster_name = result
    details = dict(item.details or {})
    namespace = 'Cluster-Wide' if item.storage_type in {'StorageClass', 'PersistentVolume'} else (item.namespace or '-')
    requested_storage = format_kubernetes_size(details.get('requested_storage')) if details.get('requested_storage') else '-'
    lifecycle_label, lifecycle_tone = _storage_lifecycle(item.storage_type, item.status)

    if item.storage_type == 'PersistentVolume':
        binding_reference = (
            f'{details.get("claim_namespace")}/{details.get("claim_name")}'
            if details.get('claim_namespace') and details.get('claim_name')
            else 'Unbound'
        )
    elif item.storage_type == 'PersistentVolumeClaim':
        binding_reference = details.get('volume_name') or 'Unbound'
    else:
        binding_reference = 'Provisioning Class'

    claims, claim_count, claims_truncated, pods, pod_count, pods_truncated = _related_storage_resources(item)
    parameters = {str(key): str(value) for key, value in sorted((details.get('parameters') or {}).items())}
    selector = {str(key): str(value) for key, value in sorted((details.get('selector') or {}).items())}
    labels = {str(key): str(value) for key, value in sorted((details.get('labels') or {}).items())}
    annotations = {str(key): str(value) for key, value in sorted((details.get('annotations') or {}).items())}
    mount_options = {f'Mount Option {index}': value for index, value in enumerate(details.get('mount_options') or [], start=1)}

    return {
        'id': item.id,
        'cluster_id': item.cluster_id,
        'cluster_name': cluster_name,
        'namespace': namespace,
        'name': item.name,
        'type': item.storage_type,
        'type_label': _STORAGE_TYPE_LABELS.get(item.storage_type, item.storage_type),
        'type_description': STORAGE_TYPE_DESCRIPTIONS.get(item.storage_type, 'Kubernetes storage metadata from the latest inventory snapshot.'),
        'storage_class': item.storage_class or 'Not Reported',
        'capacity': format_kubernetes_size(item.capacity) or '-',
        'requested_storage': requested_storage,
        'status': item.status or 'Unknown',
        'lifecycle_label': lifecycle_label,
        'lifecycle_tone': lifecycle_tone,
        'uid': details.get('uid') or '-',
        'finalizers': details.get('finalizers') or [],
        'access_modes': details.get('access_modes') or [],
        'volume_mode': details.get('volume_mode') or '-',
        'reclaim_policy': details.get('reclaim_policy') or 'Not Reported',
        'binding_mode': details.get('volume_binding_mode') or 'Not Reported',
        'allow_expansion': bool(details.get('allow_volume_expansion')),
        'provisioner': details.get('provisioner') or 'Not Reported',
        'parameters': parameters,
        'mount_options': mount_options,
        'allowed_topology_count': int(details.get('allowed_topology_count') or 0),
        'is_default': bool(details.get('is_default')),
        'node_affinity_configured': bool(details.get('node_affinity_configured')),
        'source': details.get('source') or {},
        'selector': selector,
        'data_source': details.get('data_source') or '-',
        'conditions': details.get('conditions') or [],
        'binding_reference': binding_reference,
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'claim_count': claim_count,
        'claims': claims,
        'claims_truncated': claims_truncated,
        'pod_count': pod_count,
        'pods': pods,
        'pods_truncated': pods_truncated,
        'labels': labels,
        'annotations': annotations,
        'operational_context': _storage_operational_context(item, lifecycle_label),
    }


def get_storage_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(StorageInventory.namespace).filter(StorageInventory.namespace.is_not(None), StorageInventory.namespace != '')
    query = filter_current_generation(query, StorageInventory)
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    return [row[0] for row in query.distinct().order_by(StorageInventory.namespace).all() if row[0]]


def get_storage_filter_types(cluster_id: str | None = None, namespace: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(StorageInventory.storage_type), StorageInventory)
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    return [row[0] for row in query.distinct().order_by(StorageInventory.storage_type).all() if row[0]]


def get_storage_filter_statuses(cluster_id: str | None = None, namespace: str | None = None, storage_type: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(StorageInventory.status), StorageInventory)
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    if storage_type:
        query = query.filter(StorageInventory.storage_type == storage_type)
    return [row[0] for row in query.distinct().order_by(StorageInventory.status).all() if row[0]]


def get_storage_inventory_view(
    cluster_id=None,
    namespace=None,
    storage_type=None,
    status=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = db.session.query(
        StorageInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == StorageInventory.cluster_id)
    query = filter_current_generation(query, StorageInventory)
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
                StorageInventory.details.cast(db.String).ilike(pattern),
            )
        )

    aggregate_rows = query.with_entities(
        StorageInventory.storage_type,
        StorageInventory.status,
        func.count(StorageInventory.id),
    ).group_by(StorageInventory.storage_type, StorageInventory.status).all()
    rows, pagination = paginate_query(
        query.order_by(Cluster.name, StorageInventory.storage_type, StorageInventory.name),
        page=page,
        per_page=per_page,
    )

    counts: dict[tuple[str, str], int] = {(str(item_type), str(item_status or 'Unknown')): int(count or 0) for item_type, item_status, count in aggregate_rows}
    type_counts = {
        item_type: sum(count for (row_type, _), count in counts.items() if row_type == item_type)
        for item_type in _STORAGE_TYPE_LABELS
    }
    bound_volumes = counts.get(('PersistentVolume', 'Bound'), 0)
    available_volumes = counts.get(('PersistentVolume', 'Available'), 0)
    bound_claims = counts.get(('PersistentVolumeClaim', 'Bound'), 0)
    pending_claims = counts.get(('PersistentVolumeClaim', 'Pending'), 0)
    lifecycle_exceptions = sum(
        count
        for (row_type, row_status), count in counts.items()
        if row_type != 'StorageClass' and row_status in {'Pending', 'Released', 'Failed', 'Lost'}
    )

    data: list[dict[str, Any]] = []
    for item, cluster_name, cluster_environment in rows:
        details = item.details or {}
        namespace_display = 'Cluster-Wide' if item.storage_type in {'StorageClass', 'PersistentVolume'} else (item.namespace or '-')
        lifecycle_label, lifecycle_tone = _storage_lifecycle(item.storage_type, item.status)
        if item.storage_type == 'StorageClass':
            provisioning_primary = details.get('provisioner') or 'Provisioner Not Reported'
            provisioning_secondary = f'{details.get("volume_binding_mode") or "Binding Mode Not Reported"}'
            capacity_primary = 'Dynamic Provisioning'
            capacity_secondary = 'Expansion Allowed' if details.get('allow_volume_expansion') else 'Expansion Not Reported'
            binding_secondary = f'{details.get("reclaim_policy") or "Reclaim Policy Not Reported"} · {details.get("volume_binding_mode") or "Binding Mode Not Reported"}'
        elif item.storage_type == 'PersistentVolume':
            provisioning_primary = item.storage_class or 'StorageClass Not Reported'
            provisioning_secondary = str((details.get('source') or {}).get('type') or 'Volume Source Not Reported')
            capacity_primary = format_kubernetes_size(item.capacity) or '-'
            access_modes = details.get('access_modes') or []
            capacity_secondary = ', '.join(access_modes) if access_modes else 'Access Modes Not Reported'
            binding_secondary = (
                f'{details.get("claim_namespace")}/{details.get("claim_name")}'
                if details.get('claim_namespace') and details.get('claim_name')
                else 'Unbound'
            )
        else:
            provisioning_primary = item.storage_class or 'StorageClass Not Reported'
            provisioning_secondary = 'PersistentVolumeClaim'
            requested = format_kubernetes_size(details.get('requested_storage')) if details.get('requested_storage') else '-'
            capacity_primary = f'Requested {requested}'
            capacity_secondary = f'Bound {format_kubernetes_size(item.capacity) or "-"}' if item.capacity else 'Bound Capacity Not Reported'
            binding_secondary = details.get('volume_name') or 'Waiting for Volume'

        data.append(
            {
                'id': item.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': namespace_display,
                'name': item.name,
                'type': item.storage_type,
                'type_display': _STORAGE_TYPE_LABELS.get(item.storage_type, item.storage_type),
                'identity_supporting': f'{_STORAGE_TYPE_LABELS.get(item.storage_type, item.storage_type)} · Age {format_age(item.created_at)}',
                'provisioning_primary': provisioning_primary,
                'provisioning_secondary': provisioning_secondary,
                'capacity_primary': capacity_primary,
                'capacity_secondary': capacity_secondary,
                'lifecycle_label': lifecycle_label,
                'lifecycle_tone': lifecycle_tone,
                'binding_secondary': binding_secondary,
                'is_default': bool(details.get('is_default')),
            }
        )

    scope_label = 'All Clusters'
    if cluster_id:
        scope_label = db.session.query(Cluster.name).filter(Cluster.id == cluster_id).scalar() or 'Selected Cluster'
    overall_posture = 'Critical' if any(status in {'Failed', 'Lost'} and count for (_, status), count in counts.items()) else ('Attention' if lifecycle_exceptions else ('Stable' if pagination['total_items'] else 'No Data'))
    overall_tone = 'critical' if overall_posture == 'Critical' else ('warning' if overall_posture == 'Attention' else ('normal' if overall_posture == 'Stable' else 'unknown'))

    return {
        'total_storage': pagination['total_items'],
        'storage_classes': type_counts.get('StorageClass', 0),
        'persistent_volumes': type_counts.get('PersistentVolume', 0),
        'persistent_volume_claims': type_counts.get('PersistentVolumeClaim', 0),
        'resource_type_count': sum(1 for value in type_counts.values() if value > 0),
        'scope_label': scope_label,
        'overall_posture': overall_posture,
        'overall_posture_tone': overall_tone,
        'bound_resource_count': bound_volumes + bound_claims,
        'exception_count': lifecycle_exceptions,
        'bound_volumes': bound_volumes,
        'available_volumes': available_volumes,
        'bound_claims': bound_claims,
        'pending_claims': pending_claims,
        'lifecycle_exceptions': lifecycle_exceptions,
        'storage_items': data,
        'pagination': pagination,
    }
