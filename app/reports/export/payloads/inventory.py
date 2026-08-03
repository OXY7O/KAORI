from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.inventory.formatting import format_kubernetes_size
from app.models import (
    Cluster,
    ClusterInventory,
    ConfigurationInventory,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)
from app.models.report import Report
from app.reports.catalog import require_selected_cluster
from app.reports.export.payloads.common import get_report_selected_cluster

InventoryRowBuilder = Callable[[Any, str, str], dict[str, Any]]
InventoryStatusBuilder = Callable[[Any], str]
InventoryTypeBuilder = Callable[[Any], str]


def _text(value: Any, fallback: str = '-') -> str:
    rendered = str(value or '').strip()
    return rendered or fallback


def _bool_label(value: bool | None, *, true_label: str = 'Yes', false_label: str = 'No') -> str:
    if value is None:
        return 'Not Available'
    return true_label if value else false_label


def _formatted_size(value: Any) -> str | None:
    rendered = format_kubernetes_size(value)
    return None if rendered == '-' else rendered


def _count_json(value: Any) -> int:
    if isinstance(value, (dict, list, tuple, set)):
        return len(value)
    return 0


def _join_json(value: Any, fallback: str = 'Not Available', limit: int = 3) -> str:
    if isinstance(value, dict):
        items = [f'{key}={item}' for key, item in sorted(value.items())]
    elif isinstance(value, (list, tuple, set)):
        items = [str(item) for item in value]
    else:
        return fallback
    if not items:
        return fallback
    rendered = ', '.join(items[:limit])
    if len(items) > limit:
        rendered += f' (+{len(items) - limit})'
    return rendered


def _node_row(item: NodeInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    status = 'Not Ready' if item.status == 'NotReady' else _text(item.status, 'Unknown')
    return {
        'status': status,
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'name': item.node_name,
        'node': item.node_name,
        'resource_type': _text(item.role, 'Worker'),
        'role': _text(item.role, 'Worker'),
        'ready': status,
        'inventory_status': 'Current',
        'scheduling_state': _bool_label(
            item.unschedulable,
            true_label='Unschedulable',
            false_label='Schedulable',
        ),
        'unschedulable': _bool_label(item.unschedulable, true_label='Unschedulable', false_label='Schedulable'),
        'cpu': item.cpu,
        'memory': _formatted_size(item.memory),
        'ephemeral_storage': _formatted_size(item.ephemeral_storage),
        'internal_ip': _text(item.internal_ip, 'Not Available'),
        'external_ip': _text(item.external_ip, 'Not Available'),
        'kubelet_version': _text(item.kubelet_version, 'Not Available'),
        'operating_system': _text(item.operating_system or item.os_image, 'Not Available'),
        'architecture': _text(item.architecture, 'Not Available'),
        'container_runtime': _text(item.container_runtime, 'Not Available'),
        'memory_pressure': _text(item.memory_pressure, 'Not Available'),
        'disk_pressure': _text(item.disk_pressure, 'Not Available'),
        'pid_pressure': _text(item.pid_pressure, 'Not Available'),
        'network_unavailable': _text(item.network_unavailable, 'Not Available'),
        'taints': _join_json(item.taints),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _namespace_row(item: NamespaceInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    return {
        'status': _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'name': item.namespace,
        'namespace': item.namespace,
        'resource_type': 'Namespace',
        'uid': _text(item.uid, 'Not Available'),
        'labels': _count_json(item.labels),
        'annotations': _count_json(item.annotations),
        'limit_ranges': item.limit_range_count,
        'network_policies': item.network_policy_count,
        'service_accounts': item.service_account_count,
        'default_service_account': _bool_label(item.default_service_account_present),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _workload_row(item: WorkloadInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = item.details or {}
    return {
        'status': _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.name,
        'resource_type': item.workload_type,
        'ready': _text(item.ready, 'Not Reported'),
        'update_strategy': _text(details.get('update_strategy') or details.get('strategy'), 'Not Available'),
        'desired_replicas': details.get('desired_replicas') if details.get('desired_replicas') is not None else details.get('replicas'),
        'available_replicas': details.get('available_replicas'),
        'updated_replicas': details.get('updated_replicas'),
        'unavailable_replicas': details.get('unavailable_replicas'),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _pod_row(item: PodInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = item.details or {}
    return {
        'status': _text(item.phase, 'Unknown'),
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.pod_name,
        'pod': item.pod_name,
        'resource_type': _text(item.workload_type, 'Standalone'),
        'workload': _text(item.workload_name, 'Standalone'),
        'node': _text(item.node_name, 'Unscheduled'),
        'pod_ip': _text(item.pod_ip, 'Not Available'),
        'ready': _text(item.ready, 'Not Reported'),
        'restarts': item.restart_count,
        'container_count': len(item.container_names or []),
        'image_count': item.image_count or len(item.container_images or []),
        'configuration_references': len(item.configuration_references or []),
        'persistent_volume_claims': len(item.persistent_volume_claims or []),
        'qos_class': _text(details.get('qos_class'), 'Not Available'),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _service_row(item: ServiceInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = item.details or {}
    return {
        'status': 'Discovered',
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.service_name,
        'resource_type': _text(item.service_type, 'Unknown'),
        'cluster_ip': _text(item.cluster_ip, 'Not Available'),
        'external_ip': _text(item.external_ip, 'Not Available'),
        'ports': _text(item.ports, 'Not Available'),
        'selector_count': _count_json(item.selector),
        'selector': _join_json(item.selector),
        'load_balancer': _text(details.get('load_balancer') or details.get('load_balancer_ip'), 'Not Available'),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _ingress_row(item: IngressInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = item.details or {}
    return {
        'status': 'TLS Enabled' if item.tls_enabled else 'TLS Disabled',
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.ingress_name,
        'resource_type': _text(item.ingress_class, 'Default Class'),
        'ingress_class': _text(item.ingress_class, 'Default Class'),
        'host': _text(item.host, 'Not Available'),
        'address': _text(item.address, 'Not Available'),
        'tls_enabled': bool(item.tls_enabled),
        'backend_count': len(item.backend_paths or []),
        'backend_paths': item.backend_paths or [],
        'tls_secret_count': len(details.get('tls') or details.get('tls_secrets') or []),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _storage_row(item: StorageInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    namespace = item.namespace or 'Cluster-Wide'
    details = item.details or {}
    return {
        'status': _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': namespace,
        'name': item.name,
        'resource_type': item.storage_type,
        'storage_class': _text(item.storage_class, 'Not Available'),
        'capacity': _formatted_size(item.capacity),
        'access_modes': _join_json(details.get('access_modes')),
        'reclaim_policy': _text(details.get('reclaim_policy'), 'Not Available'),
        'volume_mode': _text(details.get('volume_mode'), 'Not Available'),
        'claim_name': _text(details.get('claim_name') or details.get('claim'), 'Not Available'),
        'provisioner': _text(details.get('provisioner'), 'Not Available'),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _configuration_row(
    item: ConfigurationInventory,
    cluster_name: str,
    environment: str,
) -> dict[str, Any]:
    return {
        'status': 'Current',
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.name,
        'resource_type': _text(item.object_type, 'Unknown'),
        'secret_type': _text(item.secret_type, 'Not Available'),
        'key_count': item.key_count,
        'key_names': item.key_names or [],
        'immutable': item.immutable,
        'payload_size_bytes': item.payload_size_bytes,
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


_INVENTORY_REPORT_CONFIG: dict[str, dict[str, Any]] = {
    'node_inventory': {
        'model': NodeInventory,
        'asset_label': 'Nodes',
        'row_builder': _node_row,
        'status_builder': lambda item: 'Not Ready' if item.status == 'NotReady' else _text(item.status, 'Unknown'),
        'type_builder': lambda item: _text(item.role, 'Worker'),
    },
    'namespace_inventory': {
        'model': NamespaceInventory,
        'asset_label': 'Namespaces',
        'row_builder': _namespace_row,
        'status_builder': lambda item: _text(item.status, 'Unknown'),
        'type_builder': lambda _item: 'Namespace',
    },
    'workload_inventory': {
        'model': WorkloadInventory,
        'asset_label': 'Workloads',
        'row_builder': _workload_row,
        'status_builder': lambda item: _text(item.status, 'Unknown'),
        'type_builder': lambda item: _text(item.workload_type, 'Unknown'),
    },
    'pod_inventory': {
        'model': PodInventory,
        'asset_label': 'Pods',
        'row_builder': _pod_row,
        'status_builder': lambda item: _text(item.phase, 'Unknown'),
        'type_builder': lambda item: _text(item.workload_type, 'Standalone'),
    },
    'service_inventory': {
        'model': ServiceInventory,
        'asset_label': 'Services',
        'row_builder': _service_row,
        'status_builder': lambda _item: 'Discovered',
        'type_builder': lambda item: _text(item.service_type, 'Unknown'),
    },
    'ingress_inventory': {
        'model': IngressInventory,
        'asset_label': 'Ingresses',
        'row_builder': _ingress_row,
        'status_builder': lambda item: 'TLS Enabled' if item.tls_enabled else 'TLS Disabled',
        'type_builder': lambda item: _text(item.ingress_class, 'Default Class'),
    },
    'configuration_inventory': {
        'model': ConfigurationInventory,
        'asset_label': 'Configuration Assets',
        'row_builder': _configuration_row,
        'status_builder': lambda _item: 'Current',
        'type_builder': lambda item: _text(item.object_type, 'Unknown'),
    },
    'storage_inventory': {
        'model': StorageInventory,
        'asset_label': 'Storage Assets',
        'row_builder': _storage_row,
        'status_builder': lambda item: _text(item.status, 'Unknown'),
        'type_builder': lambda item: _text(item.storage_type, 'Unknown'),
    },
}

_OVERVIEW_MODELS: tuple[tuple[str, Any, str], ...] = (
    ('clusters', ClusterInventory, 'Clusters'),
    ('nodes', NodeInventory, 'Nodes'),
    ('namespaces', NamespaceInventory, 'Namespaces'),
    ('workloads', WorkloadInventory, 'Workloads'),
    ('pods', PodInventory, 'Pods'),
    ('services', ServiceInventory, 'Services'),
    ('ingresses', IngressInventory, 'Ingresses'),
    ('configuration', ConfigurationInventory, 'Configuration'),
    ('storage', StorageInventory, 'Storage'),
)


def _apply_scope(query: Any, model: Any, report: Report) -> Any:
    cluster_id = require_selected_cluster(report)
    query = filter_current_generation(query, model)
    query = query.filter(model.cluster_id == cluster_id)
    if report.namespace and hasattr(model, 'namespace'):
        query = query.filter(model.namespace == report.namespace)
    return query


def _order_columns(model: Any) -> list[Any]:
    columns: list[Any] = []
    for field_name in ('namespace', 'node_name', 'name', 'pod_name', 'service_name', 'ingress_name'):
        field = getattr(model, field_name, None)
        if field is not None:
            columns.append(field.asc())
    return columns


def _selected_cluster(report: Report) -> Cluster:
    return get_report_selected_cluster(report)


def _cluster_payload(cluster: Cluster) -> dict[str, Any]:
    return {
        'id': str(cluster.id),
        'name': cluster.name,
        'environment': str(cluster.environment or ''),
        'status': str(cluster.status or ''),
    }


def _latest_collected_at(rows: Iterable[Any]) -> datetime | None:
    values = [item.collected_at for item in rows if getattr(item, 'collected_at', None) is not None]
    return max(values) if values else None


def _collect_overview_payload(report: Report) -> dict[str, Any]:
    selected_cluster = _selected_cluster(report)
    counts: dict[str, int] = {}
    collected_values: list[datetime] = []
    by_cluster: Counter[str] = Counter()

    overview_rows: list[dict[str, Any]] = []
    for key, model, label in _OVERVIEW_MODELS:
        query = db.session.query(
            model,
            Cluster.name.label('cluster_name'),
            Cluster.environment.label('cluster_environment'),
        ).join(Cluster, Cluster.id == model.cluster_id)
        query = _apply_scope(query, model, report)
        results = query.all()
        counts[key] = len(results)
        cluster_names = {cluster_name for _item, cluster_name, _environment in results}
        namespace_names = {
            str(getattr(item, 'namespace', '') or '').strip()
            for item, _cluster_name, _environment in results
            if str(getattr(item, 'namespace', '') or '').strip()
        }
        category_collected_at = _latest_collected_at(
            item for item, _cluster_name, _environment in results
        )
        by_cluster.update(cluster_name for _item, cluster_name, _environment in results)
        collected_values.extend(
            item.collected_at
            for item, _cluster_name, _environment in results
            if getattr(item, 'collected_at', None) is not None
        )
        overview_rows.append(
            {
                'resource_type': label,
                'assets': len(results),
                'status': 'Current' if results else 'No Data',
                'cluster_scope': len(cluster_names),
                'namespace_scope': len(namespace_names),
                'collected_at': category_collected_at,
            }
        )

    node_query = db.session.query(NodeInventory)
    node_query = _apply_scope(node_query, NodeInventory, report)
    node_rows = node_query.all()
    ready_nodes = sum(1 for item in node_rows if _text(item.status).lower() == 'ready')
    not_ready_nodes = sum(1 for item in node_rows if _text(item.status).lower() in {'notready', 'not ready'})

    aggregate_rows = overview_rows
    collected_at = max(collected_values) if collected_values else None

    return {
        'cluster': _cluster_payload(selected_cluster),
        'selected_namespace': report.namespace or 'All Namespaces',
        'inventory_status': {
            'label': 'Inventory Snapshot',
            'status': 'Current' if any(counts.values()) else 'No Data',
            'description': 'Committed Kubernetes inventory totals across the selected reporting boundary.',
        },
        'summary': {
            'asset_type': 'Inventory Overview',
            'total_assets': sum(counts.values()),
            'clusters': counts.get('clusters', 0),
            'namespaces': counts.get('namespaces', 0),
            'snapshot_status': 'Current' if any(counts.values()) else 'No Data',
            'collected_at': collected_at,
        },
        'inventory_summary': {
            'asset_type': 'Inventory Overview',
            'total_assets': sum(counts.values()),
            'cluster_scope': counts.get('clusters', 0),
            'namespace_scope': counts.get('namespaces', 0),
            'distinct_statuses': 2 if node_rows else 0,
            'distinct_types': len([value for value in counts.values() if value > 0]),
            'collected_at': collected_at,
        },
        'inventory_overview': {
            **counts,
            'ready_nodes': ready_nodes,
            'not_ready_nodes': not_ready_nodes,
            'node_readiness_percent': (ready_nodes / len(node_rows) * 100.0) if node_rows else None,
        },
        'inventory_distribution': {
            'by_cluster': [
                {'cluster': label, 'assets': count}
                for label, count in sorted(by_cluster.items())
            ],
            'by_status': [
                {'status': 'Ready Nodes', 'assets': ready_nodes},
                {'status': 'Not Ready Nodes', 'assets': not_ready_nodes},
            ],
            'by_type': aggregate_rows,
        },
        'inventory_assets': aggregate_rows,
        'collected_at': collected_at,
        'generated_at': datetime.now(UTC),
    }


def get_report_kubernetes_inventory_payload(report: Report) -> dict[str, Any]:
    get_report_selected_cluster(report)
    if report.report_type == 'inventory_overview':
        try:
            return _collect_overview_payload(report)
        except Exception as exc:
            return {'_error': str(exc)}

    config = _INVENTORY_REPORT_CONFIG.get(report.report_type)
    if config is None:
        return {'_error': 'Unsupported Kubernetes inventory report type.'}

    try:
        model = config['model']
        query = db.session.query(
            model,
            Cluster.name.label('cluster_name'),
            Cluster.environment.label('cluster_environment'),
        ).join(Cluster, Cluster.id == model.cluster_id)
        query = _apply_scope(query, model, report)

        order_columns = [Cluster.name.asc(), *_order_columns(model)]
        results = query.order_by(*order_columns).all()
        row_builder: InventoryRowBuilder = config['row_builder']
        status_builder: InventoryStatusBuilder = config['status_builder']
        type_builder: InventoryTypeBuilder = config['type_builder']

        rows = [
            row_builder(item, cluster_name, cluster_environment)
            for item, cluster_name, cluster_environment in results
        ]
        status_counts = Counter(status_builder(item) for item, _cluster_name, _environment in results)
        type_counts = Counter(type_builder(item) for item, _cluster_name, _environment in results)
        cluster_counts = Counter(cluster_name for _item, cluster_name, _environment in results)
        namespace_count = len(
            {
                str(getattr(item, 'namespace', '') or '')
                for item, _cluster_name, _environment in results
                if str(getattr(item, 'namespace', '') or '').strip()
            }
        )
        collected_at = _latest_collected_at(item for item, _cluster_name, _environment in results)
        selected_cluster = _selected_cluster(report)
        asset_label = str(config['asset_label'])

        return {
            'cluster': _cluster_payload(selected_cluster),
            'selected_namespace': report.namespace or 'All Namespaces',
            'inventory_status': {
                'label': 'Inventory Snapshot',
                'status': 'Current' if rows else 'No Data',
                'description': (
                    f'{len(rows)} {asset_label.lower()} loaded from the latest committed inventory snapshot.'
                    if rows
                    else f'No {asset_label.lower()} were found in the selected inventory scope.'
                ),
            },
            'summary': {
                'asset_type': asset_label,
                'total_assets': len(rows),
                'clusters': len(cluster_counts),
                'namespaces': namespace_count,
                'snapshot_status': 'Current' if rows else 'No Data',
                'collected_at': collected_at,
            },
            'inventory_summary': {
                'asset_type': asset_label,
                'total_assets': len(rows),
                'cluster_scope': len(cluster_counts),
                'namespace_scope': namespace_count,
                'distinct_statuses': len(status_counts),
                'distinct_types': len(type_counts),
                'collected_at': collected_at,
            },
            'inventory_distribution': {
                'by_cluster': [
                    {'cluster': label, 'assets': count}
                    for label, count in sorted(cluster_counts.items())
                ],
                'by_status': [
                    {'status': label, 'assets': count}
                    for label, count in sorted(status_counts.items())
                ],
                'by_type': [
                    {'resource_type': label, 'assets': count}
                    for label, count in sorted(type_counts.items())
                ],
            },
            'inventory_assets': rows,
                'collected_at': collected_at,
            'generated_at': datetime.now(UTC),
        }
    except Exception as exc:
        return {'_error': str(exc)}
