from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.inventory.formatting import format_kubernetes_size
from app.models import (
    Cluster,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)
from app.models.report import Report

InventoryRowBuilder = Callable[[Any, str], dict[str, Any]]
InventoryStatusBuilder = Callable[[Any], str]
InventoryTypeBuilder = Callable[[Any], str]


def _text(value: Any, fallback: str = '-') -> str:
    rendered = str(value or '').strip()
    return rendered or fallback


def _node_row(item: NodeInventory, cluster_name: str) -> dict[str, Any]:
    return {
        'status': 'Not Ready' if item.status == 'NotReady' else _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'node': item.node_name,
        'role': _text(item.role, 'Worker'),
        'cpu': item.cpu or 0,
        'memory': format_kubernetes_size(item.memory),
        'ephemeral_storage': format_kubernetes_size(item.ephemeral_storage),
    }


def _namespace_row(item: NamespaceInventory, cluster_name: str) -> dict[str, Any]:
    return {
        'status': _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'namespace': item.namespace,
        'limit_ranges': item.limit_range_count or 0,
        'network_policies': item.network_policy_count or 0,
        'service_accounts': item.service_account_count or 0,
        'default_service_account': bool(item.default_service_account_present),
    }


def _workload_row(item: WorkloadInventory, cluster_name: str) -> dict[str, Any]:
    details = item.details or {}
    return {
        'status': _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'namespace': item.namespace,
        'name': item.name,
        'resource_type': item.workload_type,
        'ready': _text(item.ready, 'Not Reported'),
        'update_strategy': _text(details.get('update_strategy') or details.get('strategy')),
    }


def _pod_row(item: PodInventory, cluster_name: str) -> dict[str, Any]:
    return {
        'status': _text(item.phase, 'Unknown'),
        'cluster': cluster_name,
        'namespace': item.namespace,
        'pod': item.pod_name,
        'node': _text(item.node_name, 'Unscheduled'),
        'ready': _text(item.ready, 'Not Reported'),
        'restarts': item.restart_count or 0,
    }


def _service_row(item: ServiceInventory, cluster_name: str) -> dict[str, Any]:
    return {
        'cluster': cluster_name,
        'namespace': item.namespace,
        'name': item.service_name,
        'resource_type': _text(item.service_type, 'Unknown'),
        'cluster_ip': _text(item.cluster_ip),
        'external_ip': _text(item.external_ip),
        'ports': _text(item.ports),
    }


def _ingress_row(item: IngressInventory, cluster_name: str) -> dict[str, Any]:
    return {
        'status': 'TLS Enabled' if item.tls_enabled else 'TLS Disabled',
        'cluster': cluster_name,
        'namespace': item.namespace,
        'name': item.ingress_name,
        'resource_type': _text(item.ingress_class, 'Default Class'),
        'host': _text(item.host),
        'address': _text(item.address),
    }


def _storage_row(item: StorageInventory, cluster_name: str) -> dict[str, Any]:
    namespace = item.namespace or 'Cluster-Wide'
    return {
        'status': _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'namespace': namespace,
        'name': item.name,
        'resource_type': item.storage_type,
        'storage_class': _text(item.storage_class),
        'capacity': format_kubernetes_size(item.capacity),
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
    'storage_inventory': {
        'model': StorageInventory,
        'asset_label': 'Storage Assets',
        'row_builder': _storage_row,
        'status_builder': lambda item: _text(item.status, 'Unknown'),
        'type_builder': lambda item: _text(item.storage_type, 'Unknown'),
    },
}


def get_report_kubernetes_inventory_payload(report: Report) -> dict[str, Any]:
    config = _INVENTORY_REPORT_CONFIG.get(report.report_type)
    if config is None:
        return {'_error': 'Unsupported Kubernetes inventory report type.'}

    try:
        model = config['model']
        query = db.session.query(model, Cluster.name.label('cluster_name')).join(
            Cluster,
            Cluster.id == model.cluster_id,
        )
        query = filter_current_generation(query, model)

        if report.cluster_id:
            query = query.filter(model.cluster_id == report.cluster_id)

        if report.namespace and hasattr(model, 'namespace'):
            query = query.filter(model.namespace == report.namespace)

        order_columns = [Cluster.name.asc()]
        for field_name in ('namespace', 'node_name', 'name', 'pod_name', 'service_name', 'ingress_name'):
            field = getattr(model, field_name, None)
            if field is not None:
                order_columns.append(field.asc())

        results = query.order_by(*order_columns).all()
        row_builder: InventoryRowBuilder = config['row_builder']
        status_builder: InventoryStatusBuilder = config['status_builder']
        type_builder: InventoryTypeBuilder = config['type_builder']

        rows = [row_builder(item, cluster_name) for item, cluster_name in results]
        status_counts = Counter(status_builder(item) for item, _cluster_name in results)
        type_counts = Counter(type_builder(item) for item, _cluster_name in results)
        cluster_counts = Counter(cluster_name for _item, cluster_name in results)
        namespace_count = len(
            {
                str(getattr(item, 'namespace', '') or '')
                for item, _cluster_name in results
                if str(getattr(item, 'namespace', '') or '').strip()
            }
        )
        collected_values = [
            item.collected_at
            for item, _cluster_name in results
            if getattr(item, 'collected_at', None) is not None
        ]
        collected_at = max(collected_values) if collected_values else None
        selected_cluster = db.session.get(Cluster, report.cluster_id) if report.cluster_id else None
        asset_label = str(config['asset_label'])

        return {
            'cluster': (
                {
                    'id': str(selected_cluster.id),
                    'name': selected_cluster.name,
                    'environment': str(selected_cluster.environment or ''),
                    'status': str(selected_cluster.status or ''),
                }
                if selected_cluster is not None
                else None
            ),
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
