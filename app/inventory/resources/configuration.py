from __future__ import annotations

from typing import Any

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.formatting import format_byte_count
from app.inventory.resources.common import _pod_summary, format_age
from app.models import Cluster, ConfigurationInventory, PodInventory


def get_configuration_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(ConfigurationInventory.namespace)
    query = filter_current_generation(query, ConfigurationInventory)
    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)

    return [
        namespace for (namespace,) in query.distinct().order_by(ConfigurationInventory.namespace).all() if namespace
    ]


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
    ).join(Cluster, Cluster.id == ConfigurationInventory.cluster_id)
    query = filter_current_generation(query, ConfigurationInventory)

    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ConfigurationInventory.namespace == namespace)
    if object_type:
        query = query.filter(ConfigurationInventory.object_type == object_type)
    if search:
        query = query.filter(ConfigurationInventory.name.ilike(f'%{search}%'))

    summary_rows = query.with_entities(
        ConfigurationInventory.object_type,
        ConfigurationInventory.immutable,
    ).all()
    rows, pagination = paginate_query(
        query.order_by(
            Cluster.name,
            ConfigurationInventory.namespace,
            ConfigurationInventory.object_type,
            ConfigurationInventory.name,
        ),
        page=page,
        per_page=per_page,
    )

    items = [
        {
            'id': item.id,
            'cluster_name': cluster_name,
            'namespace': item.namespace,
            'name': item.name,
            'type': item.object_type,
            'secret_type': item.secret_type,
            'key_count': item.key_count,
            'immutable': item.immutable,
            'payload_size': format_byte_count(item.payload_size_bytes),
            'age': format_age(item.created_at),
        }
        for item, cluster_name in rows
    ]

    return {
        'total_items': pagination['total_items'],
        'config_maps': sum(1 for item_type, _ in summary_rows if item_type == 'ConfigMap'),
        'secrets': sum(1 for item_type, _ in summary_rows if item_type == 'Secret'),
        'immutable_items': sum(1 for _, immutable in summary_rows if immutable),
        'items': items,
        'pagination': pagination,
    }


def get_configuration_detail(
    configuration_id: int,
) -> dict[str, Any] | None:
    query = db.session.query(
        ConfigurationInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == ConfigurationInventory.cluster_id)
    query = filter_current_generation(query, ConfigurationInventory)
    result = query.filter(ConfigurationInventory.id == configuration_id).first()

    if result is None:
        return None

    item, cluster_name = result
    pod_query = filter_current_generation(PodInventory.query, PodInventory)
    candidate_pods = (
        pod_query.filter_by(
            cluster_id=item.cluster_id,
            namespace=item.namespace,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )

    used_by = []
    for pod in candidate_pods:
        references = pod.configuration_references or []
        if any(
            reference.get('type') == item.object_type and reference.get('name') == item.name for reference in references
        ):
            used_by.append(
                {
                    **_pod_summary(pod),
                    'workload_type': pod.workload_type or '-',
                    'workload_name': pod.workload_name or '-',
                }
            )

    return {
        'id': item.id,
        'cluster_name': cluster_name,
        'namespace': item.namespace,
        'name': item.name,
        'type': item.object_type,
        'secret_type': item.secret_type or '-',
        'key_names': item.key_names or [],
        'key_count': item.key_count,
        'immutable': item.immutable,
        'payload_size': format_byte_count(item.payload_size_bytes),
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'used_by_count': len(used_by),
        'used_by': used_by[:8],
        'used_by_truncated': len(used_by) > 8,
    }
