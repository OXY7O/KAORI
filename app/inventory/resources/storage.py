from __future__ import annotations

from typing import Any

from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB, array

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import format_age
from app.inventory.resources.descriptions import STORAGE_TYPE_DESCRIPTIONS
from app.inventory.resources.pod_semantics import pod_operational_state
from app.inventory.resources.storage_semantics import (
    COLLECTED,
    LIFECYCLE_ORDER,
    NOT_ASSIGNED,
    NOT_CONFIGURED,
    NOT_REPORTED,
    PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY,
    PERSISTENT_VOLUME_EVIDENCE_KEY,
    STORAGE_CLASS_EVIDENCE_KEY,
    STORAGE_TYPE_LABELS,
    UNKNOWN_FILTER,
    binding_reference,
    capacity_presentation,
    collection_posture,
    data_source_presentation,
    expansion_presentation,
    lifecycle_filter_label,
    lifecycle_filter_value,
    lifecycle_presentation,
    list_presentation,
    provisioning_presentation,
    size_presentation,
)
from app.models import Cluster, ClusterInventory, PodInventory, StorageInventory


def _base_query():
    query = db.session.query(
        StorageInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == StorageInventory.cluster_id)
    return filter_current_generation(query, StorageInventory)


def _apply_filters(
    query,
    *,
    cluster_id: str | None = None,
    namespace: str | None = None,
    storage_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
):
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    if storage_type:
        query = query.filter(StorageInventory.storage_type == storage_type)
    if status == 'Configured':
        query = query.filter(StorageInventory.storage_type == 'StorageClass')
    elif status == UNKNOWN_FILTER:
        query = query.filter(
            StorageInventory.storage_type != 'StorageClass',
            or_(StorageInventory.status.is_(None), func.trim(StorageInventory.status) == ''),
        )
    elif status:
        query = query.filter(
            StorageInventory.storage_type != 'StorageClass',
            StorageInventory.status == status,
        )
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                StorageInventory.name.ilike(pattern),
                StorageInventory.namespace.ilike(pattern),
                StorageInventory.storage_type.ilike(pattern),
                StorageInventory.storage_class.ilike(pattern),
                StorageInventory.status.ilike(pattern),
                cast(StorageInventory.details, String).ilike(pattern),
            )
        )
    return query


def get_storage_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(StorageInventory.namespace), StorageInventory).filter(
        StorageInventory.storage_type == 'PersistentVolumeClaim',
        StorageInventory.namespace.is_not(None),
        StorageInventory.namespace != '',
    )
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    return [value for (value,) in query.distinct().order_by(StorageInventory.namespace).all() if value]


def get_storage_filter_types(cluster_id: str | None = None, namespace: str | None = None) -> list[str]:
    query = filter_current_generation(
        db.session.query(StorageInventory.storage_type),
        StorageInventory,
    )
    if cluster_id:
        query = query.filter(StorageInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(StorageInventory.namespace == namespace)
    values = {str(value) for (value,) in query.distinct().all() if value}
    return [value for value in STORAGE_TYPE_LABELS if value in values]


def get_storage_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
    storage_type: str | None = None,
) -> list[str]:
    query = filter_current_generation(
        db.session.query(
            StorageInventory.storage_type,
            StorageInventory.status,
            StorageInventory.details,
        ),
        StorageInventory,
    )
    query = _apply_filters(
        query,
        cluster_id=cluster_id,
        namespace=namespace,
        storage_type=storage_type,
    )
    values = {
        lifecycle_filter_value(str(item_type), item_status, details or {})
        for item_type, item_status, details in query.all()
    }
    ordered = [value for value in LIFECYCLE_ORDER if (UNKNOWN_FILTER if value == NOT_REPORTED else value) in values]
    return [UNKNOWN_FILTER if value == NOT_REPORTED else value for value in ordered]


def storage_status_filter_label(value: str) -> str:
    return lifecycle_filter_label(value)


def _scope_cluster_ids(cluster_id: str | None) -> list[str]:
    if cluster_id:
        return [cluster_id]
    return [str(value) for (value,) in db.session.query(Cluster.id).order_by(Cluster.created_at, Cluster.id).all()]


def _collection_context(cluster_id: str | None) -> dict[str, Any]:
    cluster_ids = _scope_cluster_ids(cluster_id)
    if not cluster_ids:
        return {
            'state': NOT_REPORTED,
            'tone': 'unknown',
            'exception_count': 0,
            'storage_class_state': NOT_REPORTED,
            'persistent_volume_state': NOT_REPORTED,
            'persistent_volume_claim_state': NOT_REPORTED,
        }
    rows = {
        row.cluster_id: dict(row.collection_evidence or {})
        for row in ClusterInventory.query.filter(ClusterInventory.cluster_id.in_(cluster_ids)).all()
    }
    keys = (
        STORAGE_CLASS_EVIDENCE_KEY,
        PERSISTENT_VOLUME_EVIDENCE_KEY,
        PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY,
    )
    states_by_key = {
        key: [str(rows.get(item_id, {}).get(key) or NOT_REPORTED) for item_id in cluster_ids] for key in keys
    }
    all_states = [state for states in states_by_key.values() for state in states]
    state, tone, exception_count = collection_posture(all_states)

    def family_state(key: str) -> str:
        states = states_by_key[key]
        return COLLECTED if states and all(value == COLLECTED for value in states) else NOT_REPORTED

    return {
        'state': state,
        'tone': tone,
        'exception_count': exception_count,
        'storage_class_state': family_state(STORAGE_CLASS_EVIDENCE_KEY),
        'persistent_volume_state': family_state(PERSISTENT_VOLUME_EVIDENCE_KEY),
        'persistent_volume_claim_state': family_state(PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY),
    }


def _summary_rows(
    *,
    cluster_id: str | None,
    namespace: str | None,
    storage_type: str | None,
    status: str | None,
    search: str | None,
) -> list[tuple[str, str | None, dict[str, Any]]]:
    query = filter_current_generation(
        db.session.query(
            StorageInventory.storage_type,
            StorageInventory.status,
            StorageInventory.details,
        ),
        StorageInventory,
    )
    return _apply_filters(
        query,
        cluster_id=cluster_id,
        namespace=namespace,
        storage_type=storage_type,
        status=status,
        search=search,
    ).all()


def _summary_metrics(rows: list[tuple[str, str | None, dict[str, Any]]]) -> dict[str, int]:
    metrics = {
        'storage_classes': 0,
        'persistent_volumes': 0,
        'persistent_volume_claims': 0,
        'bound_volumes': 0,
        'available_volumes': 0,
        'bound_claims': 0,
        'pending_claims': 0,
        'lifecycle_exceptions': 0,
        'not_reported_objects': 0,
        'critical_lifecycle_exceptions': 0,
    }
    for storage_type, status, details in rows:
        if storage_type == 'StorageClass':
            metrics['storage_classes'] += 1
        elif storage_type == 'PersistentVolume':
            metrics['persistent_volumes'] += 1
        elif storage_type == 'PersistentVolumeClaim':
            metrics['persistent_volume_claims'] += 1
        lifecycle, _ = lifecycle_presentation(storage_type, status, details or {})
        metrics['bound_volumes'] += int(storage_type == 'PersistentVolume' and lifecycle == 'Bound')
        metrics['available_volumes'] += int(storage_type == 'PersistentVolume' and lifecycle == 'Available')
        metrics['bound_claims'] += int(storage_type == 'PersistentVolumeClaim' and lifecycle == 'Bound')
        metrics['pending_claims'] += int(storage_type == 'PersistentVolumeClaim' and lifecycle == 'Pending')
        metrics['lifecycle_exceptions'] += int(
            storage_type != 'StorageClass' and lifecycle in {'Pending', 'Released', 'Terminating', 'Failed', 'Lost'}
        )
        metrics['not_reported_objects'] += int(lifecycle == NOT_REPORTED)
        metrics['critical_lifecycle_exceptions'] += int(lifecycle in {'Failed', 'Lost'})
    return metrics


def _present_storage_row(
    item: StorageInventory,
    cluster_name: str,
    cluster_environment: str,
) -> dict[str, Any]:
    details = dict(item.details or {})
    lifecycle_label, lifecycle_tone = lifecycle_presentation(item.storage_type, item.status, details)
    provisioning_primary, provisioning_secondary = provisioning_presentation(
        item.storage_type,
        item.storage_class,
        details,
    )
    capacity_primary, capacity_secondary = capacity_presentation(
        item.storage_type,
        item.capacity,
        details,
    )
    return {
        'id': item.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'namespace': (
            'Cluster-Wide'
            if item.storage_type in {'StorageClass', 'PersistentVolume'}
            else str(item.namespace or NOT_REPORTED)
        ),
        'name': item.name,
        'type': item.storage_type,
        'type_display': STORAGE_TYPE_LABELS.get(item.storage_type, item.storage_type),
        'identity_supporting': STORAGE_TYPE_LABELS.get(item.storage_type, item.storage_type),
        'provisioning_primary': provisioning_primary,
        'provisioning_secondary': provisioning_secondary,
        'capacity_primary': capacity_primary,
        'capacity_secondary': capacity_secondary,
        'lifecycle_label': lifecycle_label,
        'lifecycle_tone': lifecycle_tone,
        'binding_secondary': binding_reference(item.storage_type, details),
        'is_default': bool(details.get('is_default')),
    }


def _overall_posture(total: int, metrics: dict[str, int], collection: dict[str, Any]) -> tuple[str, str]:
    if metrics['critical_lifecycle_exceptions']:
        return 'Critical', 'critical'
    if metrics['lifecycle_exceptions'] or metrics['not_reported_objects']:
        return 'Attention', 'warning'
    if collection['exception_count']:
        return 'Evidence Gap', 'warning'
    if total:
        return 'Represented', 'normal'
    if collection['state'] == 'Complete':
        return 'No Objects', 'info'
    return NOT_REPORTED, 'unknown'


def get_storage_inventory_view(
    cluster_id=None,
    namespace=None,
    storage_type=None,
    status=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = _apply_filters(
        _base_query(),
        cluster_id=cluster_id,
        namespace=namespace,
        storage_type=storage_type,
        status=status,
        search=search,
    )
    rows, pagination = paginate_query(
        query.order_by(Cluster.name, StorageInventory.storage_type, StorageInventory.name),
        page=page,
        per_page=per_page,
    )
    summary_rows = _summary_rows(
        cluster_id=cluster_id,
        namespace=namespace,
        storage_type=storage_type,
        status=status,
        search=search,
    )
    metrics = _summary_metrics(summary_rows)
    collection = _collection_context(cluster_id)
    posture, posture_tone = _overall_posture(pagination['total_items'], metrics, collection)
    scope_label = 'All Clusters'
    if cluster_id:
        scope_label = db.session.query(Cluster.name).filter(Cluster.id == cluster_id).scalar() or 'Selected Cluster'
    resource_type_count = sum(
        int(metrics[key] > 0) for key in ('storage_classes', 'persistent_volumes', 'persistent_volume_claims')
    )
    binding_evidence_reported = (
        collection['persistent_volume_state'] == COLLECTED and collection['persistent_volume_claim_state'] == COLLECTED
    )
    return {
        'total_storage': pagination['total_items'],
        **metrics,
        'resource_type_count': resource_type_count,
        'scope_label': scope_label,
        'overall_posture': posture,
        'overall_posture_tone': posture_tone,
        'bound_resource_count': (
            metrics['bound_volumes'] + metrics['bound_claims'] if binding_evidence_reported else NOT_REPORTED
        ),
        'binding_evidence_reported': binding_evidence_reported,
        'exception_count': metrics['lifecycle_exceptions']
        + metrics['not_reported_objects']
        + collection['exception_count'],
        'collection': collection,
        'storage_items': [
            _present_storage_row(item, cluster_name, environment) for item, cluster_name, environment in rows
        ],
        'pagination': pagination,
    }


def _cluster_collection_states(cluster_id: str) -> dict[str, str]:
    cluster_inventory = ClusterInventory.query.filter_by(cluster_id=cluster_id).first()
    evidence = dict(cluster_inventory.collection_evidence or {}) if cluster_inventory else {}
    return {
        'storage_classes': str(evidence.get(STORAGE_CLASS_EVIDENCE_KEY) or NOT_REPORTED),
        'persistent_volumes': str(evidence.get(PERSISTENT_VOLUME_EVIDENCE_KEY) or NOT_REPORTED),
        'persistent_volume_claims': str(evidence.get(PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY) or NOT_REPORTED),
        'pods': str(evidence.get('inventory.pods') or NOT_REPORTED),
    }


def _claim_rows(item: StorageInventory, states: dict[str, str]) -> tuple[list[tuple[str, str]], bool]:
    details = item.details or {}
    if item.storage_type == 'PersistentVolumeClaim' and item.namespace:
        return [(item.namespace, item.name)], True
    if item.storage_type == 'PersistentVolume':
        if states['persistent_volumes'] != COLLECTED:
            return [], False
        namespace = details.get('claim_namespace')
        name = details.get('claim_name')
        return ([(str(namespace), str(name))] if namespace and name else []), True
    if item.storage_type == 'StorageClass':
        if states['persistent_volume_claims'] != COLLECTED:
            return [], False
        query = filter_current_generation(
            db.session.query(StorageInventory.namespace, StorageInventory.name),
            StorageInventory,
        ).filter(
            StorageInventory.cluster_id == item.cluster_id,
            StorageInventory.storage_type == 'PersistentVolumeClaim',
            StorageInventory.storage_class == item.name,
            StorageInventory.namespace.is_not(None),
        )
        return [
            (str(namespace), str(name))
            for namespace, name in query.order_by(StorageInventory.namespace, StorageInventory.name).all()
        ], True
    return [], False


def _related_storage_resources(item: StorageInventory, states: dict[str, str]) -> dict[str, Any]:
    claims, claims_reported = _claim_rows(item, states)
    claim_resources = [
        {
            'name': name,
            'supporting_primary': f'Namespace · {namespace}',
            'supporting_secondary': 'PersistentVolumeClaim reference',
            'status': None,
            'status_tone': None,
        }
        for namespace, name in claims[:8]
    ]
    pods_reported = states['pods'] == COLLECTED
    if not claims or not pods_reported:
        return {
            'claims': claim_resources,
            'claim_count': len(claims),
            'claims_truncated': len(claims) > 8,
            'claims_reported': claims_reported,
            'pods': [],
            'pod_count': 0,
            'pods_truncated': False,
            'pods_reported': pods_reported,
        }

    names_by_namespace: dict[str, set[str]] = {}
    for namespace, name in claims:
        names_by_namespace.setdefault(namespace, set()).add(name)
    pod_base_query = filter_current_generation(PodInventory.query, PodInventory).filter(
        PodInventory.cluster_id == item.cluster_id,
        PodInventory.namespace.in_(sorted(names_by_namespace)),
    )
    dialect = db.session.get_bind().dialect.name
    if dialect == 'postgresql':
        clauses = [
            and_(
                PodInventory.namespace == namespace,
                cast(PodInventory.persistent_volume_claims, JSONB).op('?|')(array(sorted(names))),
            )
            for namespace, names in names_by_namespace.items()
        ]
        pod_query = pod_base_query.filter(or_(*clauses))
        pod_count = pod_query.count()
        pod_rows = pod_query.order_by(PodInventory.namespace, PodInventory.pod_name).limit(8).all()
    else:
        candidates = pod_base_query.order_by(PodInventory.namespace, PodInventory.pod_name).all()
        matched = [
            pod
            for pod in candidates
            if names_by_namespace.get(pod.namespace, set()).intersection(set(pod.persistent_volume_claims or []))
        ]
        pod_count = len(matched)
        pod_rows = matched[:8]
    pod_resources = []
    for pod in pod_rows:
        state, tone, evidence = pod_operational_state(pod.phase, pod.ready)
        pod_resources.append(
            {
                'name': pod.pod_name,
                'supporting_primary': f'Namespace · {pod.namespace} · Node {pod.node_name or "Not Scheduled"}',
                'supporting_secondary': evidence,
                'status': state,
                'status_tone': tone,
            }
        )
    return {
        'claims': claim_resources,
        'claim_count': len(claims),
        'claims_truncated': len(claims) > 8,
        'claims_reported': claims_reported,
        'pods': pod_resources,
        'pod_count': pod_count,
        'pods_truncated': pod_count > 8,
        'pods_reported': True,
    }


def _operational_context(item: StorageInventory, lifecycle_label: str, states: dict[str, str]) -> dict[str, str]:
    if lifecycle_label == NOT_REPORTED:
        return {
            'title': 'Refresh Storage Lifecycle Evidence',
            'description': 'Kubernetes lifecycle status was not reported for this storage object. Refresh inventory before making binding decisions.',
            'tone': 'warning',
            'icon': 'refresh-cw',
        }
    if lifecycle_label == 'Terminating':
        return {
            'title': 'Validate Storage Termination',
            'description': 'Review finalizers, attached workloads, reclaim behavior, and controller events before treating deletion as complete.',
            'tone': 'warning',
            'icon': 'hourglass',
        }
    if item.storage_type == 'PersistentVolumeClaim' and lifecycle_label == 'Pending':
        return {
            'title': 'Review Claim Binding',
            'description': 'Confirm StorageClass selection, provisioner availability, topology constraints, quota, and pending volume events.',
            'tone': 'warning',
            'icon': 'link-2-off',
        }
    if item.storage_type == 'PersistentVolume' and lifecycle_label == 'Released':
        return {
            'title': 'Review Reclaim Lifecycle',
            'description': 'Confirm whether the released volume should be retained, cleaned externally, or prepared for a new claim.',
            'tone': 'warning',
            'icon': 'archive-restore',
        }
    if lifecycle_label in {'Lost', 'Failed'}:
        return {
            'title': 'Investigate Storage Failure',
            'description': 'Review binding evidence, provisioner events, volume source state, and the owning application before relying on this object.',
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
    required_state = {
        'StorageClass': states['storage_classes'],
        'PersistentVolume': states['persistent_volumes'],
        'PersistentVolumeClaim': states['persistent_volume_claims'],
    }.get(item.storage_type, NOT_REPORTED)
    if required_state != COLLECTED:
        return {
            'title': 'Refresh Storage Collection Evidence',
            'description': 'The resource family was not fully collected for this cluster. Refresh inventory before treating the snapshot as complete.',
            'tone': 'warning',
            'icon': 'refresh-cw',
        }
    return {
        'title': 'Storage Snapshot Ready for Review',
        'description': 'No exceptional lifecycle state is represented in the latest committed storage snapshot.',
        'tone': 'normal',
        'icon': 'circle-check',
    }


def _condition_rows(details: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for condition in details.get('conditions') or []:
        if not isinstance(condition, dict):
            continue
        status = str(condition.get('status') or 'Unknown')
        condition_type = str(condition.get('type') or 'Unknown')
        tone = (
            'warning' if status == 'True' and condition_type in {'Resizing', 'FileSystemResizePending'} else 'unknown'
        )
        result.append(
            {
                **condition,
                'state_label': status,
                'state_tone': tone,
            }
        )
    return result


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in sorted(value.items())}


def _mount_option_map(details: dict[str, Any]) -> dict[str, str]:
    return {
        f'Mount Option {index}': str(value) for index, value in enumerate(details.get('mount_options') or [], start=1)
    }


def _source_map(details: dict[str, Any]) -> tuple[dict[str, str], str]:
    source = details.get('source')
    if not isinstance(source, dict):
        return {}, NOT_REPORTED
    presented = {str(key): str(value) for key, value in source.items() if key != 'reported' and value not in (None, '')}
    return presented, str(source.get('type') or NOT_REPORTED)


def _detail_identity_fields(item: StorageInventory, cluster_name: str, details: dict[str, Any]) -> dict[str, Any]:
    namespace = str(item.namespace or NOT_REPORTED)
    if item.storage_type in {'StorageClass', 'PersistentVolume'}:
        namespace = 'Cluster-Wide'
    return {
        'id': item.id,
        'cluster_id': item.cluster_id,
        'cluster_name': cluster_name,
        'namespace': namespace,
        'name': item.name,
        'type': item.storage_type,
        'type_label': STORAGE_TYPE_LABELS.get(item.storage_type, item.storage_type),
        'type_description': STORAGE_TYPE_DESCRIPTIONS.get(
            item.storage_type,
            'Kubernetes storage metadata from the latest committed inventory snapshot.',
        ),
        'uid': details.get('uid') or NOT_REPORTED,
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'labels': _string_map(details.get('labels')),
        'annotations': _string_map(details.get('annotations')),
    }


def _detail_capacity_fields(item: StorageInventory, details: dict[str, Any]) -> dict[str, Any]:
    capacity_primary, capacity_supporting = capacity_presentation(
        item.storage_type,
        item.capacity,
        details,
    )
    specification_reported = details.get('specification_evidence_reported') is True
    status_reported = details.get('status_evidence_reported') is True
    if item.storage_type == 'PersistentVolumeClaim':
        requested_storage = size_presentation(
            details.get('requested_storage'),
            missing=NOT_CONFIGURED if specification_reported else NOT_REPORTED,
        )
        reported_capacity = size_presentation(
            item.capacity if details.get('capacity_evidence_reported') else None,
            missing=NOT_ASSIGNED if status_reported else NOT_REPORTED,
        )
        capacity_summary = reported_capacity
        capacity_summary_supporting = f'Requested · {requested_storage}'
    elif item.storage_type == 'PersistentVolume':
        requested_storage = 'Not Applicable'
        reported_capacity = size_presentation(
            item.capacity,
            missing=NOT_CONFIGURED if specification_reported else NOT_REPORTED,
        )
        capacity_summary = reported_capacity
        capacity_summary_supporting = capacity_supporting
    else:
        requested_storage = 'Not Applicable'
        reported_capacity = 'Not Applicable'
        capacity_summary = capacity_primary
        capacity_summary_supporting = capacity_supporting

    requested_access_modes = details.get('requested_access_modes')
    if item.storage_type == 'PersistentVolume':
        requested_access_modes = details.get('access_modes')
    return {
        'storage_class': provisioning_presentation(
            item.storage_type,
            item.storage_class,
            details,
        )[0],
        'capacity': capacity_summary,
        'capacity_supporting': capacity_summary_supporting,
        'requested_storage': requested_storage,
        'reported_capacity': reported_capacity,
        'allocated_storage': size_presentation(
            details.get('allocated_storage'),
            missing=NOT_ASSIGNED if status_reported else NOT_REPORTED,
        ),
        'requested_access_modes': list_presentation(
            requested_access_modes,
            evidence_reported=specification_reported,
        ),
        'reported_access_modes': list_presentation(
            details.get('reported_access_modes'),
            evidence_reported=status_reported,
        ),
        'volume_mode': (
            str(details.get('volume_mode'))
            if details.get('volume_mode') not in (None, '')
            else (NOT_CONFIGURED if specification_reported else NOT_REPORTED)
        ),
        'node_affinity': (
            NOT_REPORTED
            if not specification_reported
            else ('Configured' if details.get('node_affinity_configured') else NOT_CONFIGURED)
        ),
        'specification_evidence': 'Reported' if specification_reported else NOT_REPORTED,
        'status_evidence': 'Reported' if status_reported else NOT_REPORTED,
    }


def _detail_provisioning_fields(item: StorageInventory, details: dict[str, Any]) -> dict[str, Any]:
    source, source_type = _source_map(details)
    specification_reported = details.get('specification_evidence_reported') is True
    data_source = 'Not Applicable'
    if item.storage_type == 'PersistentVolumeClaim':
        data_source = data_source_presentation(details)
    reclaim_policy = 'Not Applicable'
    if item.storage_type in {'StorageClass', 'PersistentVolume'}:
        reclaim_policy = (
            str(details.get('reclaim_policy'))
            if details.get('reclaim_policy') not in (None, '')
            else (NOT_CONFIGURED if specification_reported else NOT_REPORTED)
        )
    mount_options_reported = item.storage_type == 'StorageClass' or specification_reported
    return {
        'finalizers': details.get('finalizers') or [],
        'reclaim_policy': reclaim_policy,
        'binding_mode': (
            str(details.get('volume_binding_mode') or NOT_REPORTED)
            if item.storage_type == 'StorageClass'
            else 'Not Applicable'
        ),
        'expansion': expansion_presentation(item.storage_type, details),
        'provisioner': (
            str(details.get('provisioner') or NOT_REPORTED) if item.storage_type == 'StorageClass' else 'Not Applicable'
        ),
        'parameters': _string_map(details.get('parameters')),
        'mount_options': _mount_option_map(details),
        'mount_options_reported': mount_options_reported,
        'allowed_topology_count': (
            int(details.get('allowed_topology_count') or 0) if item.storage_type == 'StorageClass' else 'Not Applicable'
        ),
        'is_default': bool(details.get('is_default')),
        'source': source,
        'source_type': source_type,
        'selector': _string_map(details.get('selector')),
        'selector_reported': specification_reported,
        'data_source': data_source,
        'conditions': _condition_rows(details),
        'binding_reference': binding_reference(item.storage_type, details),
    }


def get_storage_detail(storage_id: int) -> dict[str, Any] | None:
    query = db.session.query(StorageInventory, Cluster.name.label('cluster_name')).join(
        Cluster,
        Cluster.id == StorageInventory.cluster_id,
    )
    query = filter_current_generation(query, StorageInventory)
    result = query.filter(StorageInventory.id == storage_id).first()
    if result is None:
        return None

    item, cluster_name = result
    details = dict(item.details or {})
    states = _cluster_collection_states(item.cluster_id)
    lifecycle_label, lifecycle_tone = lifecycle_presentation(
        item.storage_type,
        item.status,
        details,
    )
    return {
        **_detail_identity_fields(item, cluster_name, details),
        **_detail_capacity_fields(item, details),
        **_detail_provisioning_fields(item, details),
        **_related_storage_resources(item, states),
        'lifecycle_label': lifecycle_label,
        'lifecycle_tone': lifecycle_tone,
        'collection_states': states,
        'operational_context': _operational_context(item, lifecycle_label, states),
    }
