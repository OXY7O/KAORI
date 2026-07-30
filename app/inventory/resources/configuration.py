from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import format_age
from app.models import Cluster, ClusterInventory, ConfigurationInventory, PodInventory


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


def _collection_state(cluster_id: str, object_type: str) -> str:
    family = 'inventory.secrets' if object_type == 'Secret' else 'inventory.configmaps'
    row = ClusterInventory.query.filter_by(cluster_id=cluster_id).first()
    return str((row.collection_evidence or {}).get(family) or 'Not Reported') if row else 'Not Reported'


def _reference_map(configuration_rows: list[tuple[int, str, str, str, str]]) -> dict[int, int]:
    if not configuration_rows:
        return {}
    lookup = {(cluster_id, namespace, object_type, name): item_id for item_id, cluster_id, namespace, object_type, name in configuration_rows}
    cluster_ids = sorted({row[1] for row in configuration_rows})
    namespaces = sorted({row[2] for row in configuration_rows})
    pod_query = filter_current_generation(PodInventory.query, PodInventory).filter(
        PodInventory.cluster_id.in_(cluster_ids),
        PodInventory.namespace.in_(namespaces),
    )
    counts: dict[int, int] = defaultdict(int)
    for pod in pod_query.with_entities(PodInventory.cluster_id, PodInventory.namespace, PodInventory.configuration_references).yield_per(250):
        for reference in pod.configuration_references or []:
            key = (pod.cluster_id, pod.namespace, reference.get('type'), reference.get('name'))
            item_id = lookup.get(key)
            if item_id is not None:
                counts[item_id] += 1
    return dict(counts)


def get_configuration_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(ConfigurationInventory.namespace), ConfigurationInventory)
    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)
    return [namespace for (namespace,) in query.distinct().order_by(ConfigurationInventory.namespace).all() if namespace]


def get_configuration_inventory_view(
    cluster_id: str | None = None,
    namespace: str | None = None,
    object_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    query = db.session.query(
        ConfigurationInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == ConfigurationInventory.cluster_id)
    query = filter_current_generation(query, ConfigurationInventory)
    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ConfigurationInventory.namespace == namespace)
    if object_type:
        query = query.filter(ConfigurationInventory.object_type == object_type)
    if search:
        pattern = f'%{search}%'
        query = query.filter(or_(ConfigurationInventory.name.ilike(pattern), ConfigurationInventory.namespace.ilike(pattern)))

    summary_rows = query.with_entities(
        ConfigurationInventory.object_type,
        ConfigurationInventory.immutable,
        ConfigurationInventory.key_count,
        func.count(ConfigurationInventory.id),
    ).group_by(ConfigurationInventory.object_type, ConfigurationInventory.immutable, ConfigurationInventory.key_count).all()

    lightweight_rows = query.with_entities(
        ConfigurationInventory.id,
        ConfigurationInventory.cluster_id,
        ConfigurationInventory.namespace,
        ConfigurationInventory.object_type,
        ConfigurationInventory.name,
    ).all()
    reference_counts = _reference_map([(int(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4])) for row in lightweight_rows])

    rows, pagination = paginate_query(
        query.order_by(Cluster.name, ConfigurationInventory.namespace, ConfigurationInventory.object_type, ConfigurationInventory.name),
        page=page,
        per_page=per_page,
    )

    config_maps = secrets = immutable_items = keyless_items = total_key_names = 0
    for item_type, immutable, key_count, count in summary_rows:
        count = int(count or 0)
        if item_type == 'ConfigMap':
            config_maps += count
        elif item_type == 'Secret':
            secrets += count
        if immutable:
            immutable_items += count
        if int(key_count or 0) == 0:
            keyless_items += count
        total_key_names += int(key_count or 0) * count

    items = []
    for item, cluster_name, cluster_environment in rows:
        reference_count = int(reference_counts.get(item.id, 0))
        type_supporting = item.secret_type or 'Protected key-index metadata' if item.object_type == 'Secret' else 'Configuration key-index metadata'
        items.append(
            {
                'id': item.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': item.namespace,
                'name': item.name,
                'type': item.object_type,
                'type_supporting': type_supporting,
                'key_count': item.key_count,
                'immutable': item.immutable,
                'mutation_label': 'Immutable' if item.immutable else 'Mutable',
                'age': format_age(item.created_at),
                'identity_supporting': f'Age {format_age(item.created_at)}',
                'reference_count': reference_count,
                'reference_label': f'{reference_count} Pod Reference' if reference_count == 1 else f'{reference_count} Pod References',
            }
        )

    current_reference_items = sum(1 for item_id, *_ in lightweight_rows if reference_counts.get(int(item_id), 0) > 0)
    no_current_reference_items = max(pagination['total_items'] - current_reference_items, 0)
    namespace_count = len({str(row[2]) for row in lightweight_rows})
    scope_label = 'All Clusters'
    if cluster_id:
        scope_label = db.session.query(Cluster.name).filter(Cluster.id == cluster_id).scalar() or 'Selected Cluster'

    evidence_rows = ClusterInventory.query
    if cluster_id:
        evidence_rows = evidence_rows.filter(ClusterInventory.cluster_id == cluster_id)
    evidence = [row.collection_evidence or {} for row in evidence_rows.all()]
    configmap_states = {str(row.get('inventory.configmaps') or 'Not Reported') for row in evidence}
    secret_states = {str(row.get('inventory.secrets') or 'Not Reported') for row in evidence}

    return {
        'total_items': pagination['total_items'],
        'config_maps': config_maps,
        'secrets': secrets,
        'immutable_items': immutable_items,
        'keyless_items': keyless_items,
        'total_key_names': total_key_names,
        'current_reference_items': current_reference_items,
        'no_current_reference_items': no_current_reference_items,
        'namespace_count': namespace_count,
        'scope_label': scope_label,
        'configmap_collection_state': ', '.join(sorted(configmap_states)) if configmap_states else 'Not Reported',
        'secret_collection_state': ', '.join(sorted(secret_states)) if secret_states else 'Not Reported',
        'items': items,
        'pagination': pagination,
    }


def get_configuration_detail(configuration_id: int) -> dict[str, Any] | None:
    query = db.session.query(ConfigurationInventory, Cluster.name.label('cluster_name')).join(
        Cluster, Cluster.id == ConfigurationInventory.cluster_id
    )
    query = filter_current_generation(query, ConfigurationInventory)
    result = query.filter(ConfigurationInventory.id == configuration_id).first()
    if result is None:
        return None

    item, cluster_name = result
    pod_query = filter_current_generation(PodInventory.query, PodInventory).filter_by(
        cluster_id=item.cluster_id,
        namespace=item.namespace,
    )
    used_by = []
    used_by_count = 0
    for pod in pod_query.order_by(PodInventory.pod_name).yield_per(100):
        references = pod.configuration_references or []
        if any(reference.get('type') == item.object_type and reference.get('name') == item.name for reference in references):
            used_by_count += 1
            if len(used_by) < 8:
                state, tone, evidence = _pod_state(pod)
                used_by.append(
                    {
                        'name': pod.pod_name,
                        'supporting_primary': f'{pod.workload_type or "Standalone"} · {pod.workload_name or "No Owner"}',
                        'supporting_secondary': evidence,
                        'status': state,
                        'status_tone': tone,
                    }
                )

    collection_state = _collection_state(item.cluster_id, item.object_type)
    if collection_state != 'Collected':
        operational_context = {
            'title': 'Review Collection Capability',
            'description': f'{item.object_type} collection is recorded as {collection_state}. Confirm Kubernetes API availability and RBAC before relying on completeness.',
            'tone': 'warning',
            'icon': 'shield-alert',
        }
    elif used_by_count == 0:
        operational_context = {
            'title': 'No Current Pod References',
            'description': 'No Pod reference is represented in the current committed snapshot. Other consumers or future workload templates may still reference this object.',
            'tone': 'info',
            'icon': 'unlink',
        }
    else:
        operational_context = {
            'title': 'Configuration Snapshot Ready for Review',
            'description': 'Key-index metadata and current Pod references are available from the latest committed inventory snapshot.',
            'tone': 'normal',
            'icon': 'circle-check',
        }

    key_entries = [(str(key), 'Key name indexed') for key in (item.key_names or [])]
    return {
        'id': item.id,
        'cluster_id': item.cluster_id,
        'cluster_name': cluster_name,
        'namespace': item.namespace,
        'name': item.name,
        'type': item.object_type,
        'secret_type': item.secret_type or 'Not Applicable',
        'key_names': item.key_names or [],
        'key_entries': key_entries,
        'key_count': item.key_count,
        'immutable': item.immutable,
        'mutation_label': 'Immutable' if item.immutable else 'Mutable',
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'used_by_count': used_by_count,
        'used_by': used_by,
        'used_by_truncated': used_by_count > 8,
        'collection_state': collection_state,
        'operational_context': operational_context,
    }
