from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.inventory.kubernetes.formatting import format_kubernetes_size
from app.inventory.kubernetes.resources.ingress_semantics import (
    host_presentation as ingress_host_presentation,
)
from app.inventory.kubernetes.resources.ingress_semantics import (
    ingress_class_presentation,
)
from app.inventory.kubernetes.resources.ingress_semantics import (
    publication_presentation as ingress_publication_presentation,
)
from app.inventory.kubernetes.resources.service_semantics import (
    access_model as service_access_model,
)
from app.inventory.kubernetes.resources.service_semantics import (
    backend_registration as service_backend_registration,
)
from app.inventory.kubernetes.resources.service_semantics import (
    effective_service_type,
)
from app.inventory.kubernetes.resources.storage_semantics import (
    NOT_CONFIGURED as STORAGE_NOT_CONFIGURED,
)
from app.inventory.kubernetes.resources.storage_semantics import (
    NOT_REPORTED as STORAGE_NOT_REPORTED,
)
from app.inventory.kubernetes.resources.storage_semantics import (
    binding_reference as storage_binding_reference,
)
from app.inventory.kubernetes.resources.storage_semantics import (
    expansion_presentation as storage_expansion_presentation,
)
from app.inventory.kubernetes.resources.storage_semantics import (
    lifecycle_presentation as storage_lifecycle_presentation,
)
from app.inventory.kubernetes.resources.storage_semantics import (
    list_presentation as storage_list_presentation,
)
from app.inventory.kubernetes.resources.storage_semantics import (
    provisioning_presentation as storage_provisioning_presentation,
)
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


def _optional_integer(value: Any) -> int | None:
    if value in (None, '', '-', 'None'):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
    update_strategy = details.get('update_strategy')
    return {
        'status': _text(item.status, 'Unknown'),
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Reported'),
        'namespace': item.namespace,
        'name': item.name,
        'resource_type': item.workload_type,
        'ready': _text(item.ready, 'Not Reported'),
        'update_strategy': _text(update_strategy, 'Not Available'),
        'desired_replicas': _optional_integer(details.get('desired_replicas')),
        'available_replicas': _optional_integer(details.get('available_replicas')),
        'updated_replicas': _optional_integer(details.get('updated_replicas')),
        'unavailable_replicas': _optional_integer(details.get('unavailable_replicas')),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _pod_row(item: PodInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = item.details or {}
    configuration = details.get('configuration') or {}
    specification_reported = details.get('specification_evidence_reported') is True
    runtime_reported = details.get('runtime_evidence_reported') is True
    configured_container_count = configuration.get('container_count')
    return {
        'status': _text(item.phase, 'Unknown'),
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.pod_name,
        'pod': item.pod_name,
        'resource_type': _text(item.workload_type, 'Standalone'),
        'workload': _text(item.workload_name, 'Standalone'),
        'node': _text(item.node_name, 'Not Scheduled'),
        'pod_ip': _text(item.pod_ip, 'Not Reported'),
        'ready': _text(item.ready, 'Not Reported'),
        'restarts': item.restart_count if runtime_reported else None,
        'container_count': configured_container_count if specification_reported else None,
        'image_count': item.image_count if specification_reported else None,
        'configuration_references': (len(item.configuration_references or []) if specification_reported else None),
        'persistent_volume_claims': (len(item.persistent_volume_claims or []) if specification_reported else None),
        'qos_class': _text(details.get('qos_class'), 'Not Reported'),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _service_port_export_value(details: dict[str, Any]) -> str:
    rows = [row for row in details.get('ports') or [] if isinstance(row, dict)]
    if not rows:
        return 'Not Configured'
    values = []
    for row in rows:
        service_port = int(row.get('port') or 0)
        protocol = _text(row.get('protocol'), 'TCP')
        target_port = _text(row.get('target_port'), str(service_port or 'Not Reported'))
        node_port = int(row.get('node_port') or 0)
        rendered = f'{service_port}/{protocol} -> {target_port}'
        if node_port:
            rendered += f' (NodePort {node_port})'
        values.append(rendered)
    return ', '.join(values) if values else 'Not Configured'


def _service_row(item: ServiceInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = item.details or {}
    effective_type = effective_service_type(item.service_type, item.cluster_ip)
    registration = service_backend_registration(
        effective_type,
        item.selector or {},
        details.get('endpoints') or {},
    )
    endpoint_applicable = effective_type != 'ExternalName'
    endpoint_reported = registration['reported'] and endpoint_applicable
    external_addresses = list(details.get('external_addresses') or [])
    load_balancer_addresses = list(details.get('load_balancer_ingress') or [])
    cluster_ip = 'None (Headless)' if effective_type == 'Headless' else _text(item.cluster_ip, 'Not Reported')
    port_rows = [row for row in details.get('ports') or [] if isinstance(row, dict)]
    load_balancer_reported = details.get('load_balancer_status_reported')
    if load_balancer_addresses:
        load_balancer_value = ', '.join(load_balancer_addresses)
    elif effective_type == 'LoadBalancer':
        load_balancer_value = 'No Address Assigned' if load_balancer_reported else 'Not Reported'
    else:
        load_balancer_value = 'Not Applicable'
    return {
        'status': registration['label'],
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.service_name,
        'resource_type': effective_type,
        'access_model': service_access_model(effective_type),
        'cluster_ip': cluster_ip,
        'external_ip': ', '.join(external_addresses) if external_addresses else 'Not Configured',
        'ports': _service_port_export_value(details),
        'port_count': len(port_rows),
        'selector_count': _count_json(item.selector),
        'selector': _join_json(item.selector, fallback='Not Configured'),
        'endpoint_source': 'Not Applicable' if not endpoint_applicable else registration['source'],
        'ready_endpoints': registration['ready'] if endpoint_reported else None,
        'not_ready_endpoints': registration['not_ready'] if endpoint_reported else None,
        'load_balancer': load_balancer_value,
        'external_name': _text(details.get('external_name'), 'Not Configured'),
        'internal_traffic_policy': _text(details.get('internal_traffic_policy'), 'Not Reported'),
        'external_traffic_policy': _text(details.get('external_traffic_policy'), 'Not Reported'),
        'publish_not_ready': bool(details.get('publish_not_ready_addresses')),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _ingress_row(item: IngressInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = item.details or {}
    ingress_class, _ = ingress_class_presentation(
        item.ingress_class,
        details.get('ingress_class_source'),
    )
    host_label, host_supporting, host_count = ingress_host_presentation(details)
    publication = ingress_publication_presentation(details)
    routes = [row for row in (item.backend_paths or []) if isinstance(row, dict)]
    service_backends = {
        str(row.get('service_name'))
        for row in routes
        if row.get('backend_type') == 'Service' and row.get('service_name')
    }
    resource_backends = sum(1 for row in routes if row.get('backend_type') == 'Resource')
    explicit_hosts = [str(value) for value in (details.get('hosts') or []) if value]
    explicit_hosts_label = (
        ', '.join(explicit_hosts)
        if explicit_hosts
        else ('Not Reported' if details.get('specification_evidence_reported') is False else 'Not Configured')
    )
    tls_entries = [row for row in (details.get('tls') or []) if isinstance(row, dict)]
    tls_secrets = {str(row.get('secret_name')) for row in tls_entries if row.get('secret_name')}
    tls_hosts = {str(host) for row in tls_entries for host in (row.get('hosts') or []) if host}
    return {
        'status': publication['label'],
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Available'),
        'namespace': item.namespace,
        'name': item.ingress_name,
        'resource_type': ingress_class,
        'ingress_class': ingress_class,
        'ingress_class_source': _text(details.get('ingress_class_source'), 'Not Reported'),
        'host_scope': host_label,
        'host_scope_supporting': host_supporting,
        'host_count': host_count,
        'hosts': explicit_hosts_label,
        'all_host_rule_count': int(details.get('hostless_rule_count') or 0),
        'publication_status': publication['label'],
        'addresses': ', '.join(publication['addresses']) if publication['addresses'] else publication['address'],
        'address_count': len(publication['addresses']) if publication['reported'] else None,
        'tls_enabled': bool(item.tls_enabled),
        'tls_status': (
            'TLS Referenced'
            if tls_secrets
            else ('TLS Declared · No Secret Reference' if tls_entries else 'No TLS Declaration')
        ),
        'tls_secret_count': len(tls_secrets),
        'tls_hosts': ', '.join(sorted(tls_hosts)) or 'Not Configured',
        'backend_count': len(routes),
        'service_backend_count': len(service_backends),
        'resource_backend_count': resource_backends,
        'backend_paths': routes,
        'created_at': item.created_at,
        'collected_at': item.collected_at,
    }


def _storage_row(item: StorageInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    namespace = item.namespace or 'Cluster-Wide'
    details = item.details or {}
    lifecycle, _ = storage_lifecycle_presentation(item.storage_type, item.status, details)
    specification_reported = details.get('specification_evidence_reported') is True
    status_reported = details.get('status_evidence_reported') is True
    storage_class_label = storage_provisioning_presentation(
        item.storage_type,
        item.storage_class,
        details,
    )[0]
    raw_source = details.get('source')
    source = raw_source if isinstance(raw_source, dict) else {}
    if item.storage_type == 'PersistentVolumeClaim':
        requested_access_modes = details.get('requested_access_modes') or []
        reported_access_modes = details.get('reported_access_modes') or []
        requested_capacity = _formatted_size(details.get('requested_storage'))
        reported_capacity = _formatted_size(item.capacity) if details.get('capacity_evidence_reported') else None
        requested_access_modes_label = storage_list_presentation(
            requested_access_modes,
            evidence_reported=specification_reported,
        )
        reported_access_modes_label = storage_list_presentation(
            reported_access_modes,
            evidence_reported=status_reported,
        )
    elif item.storage_type == 'PersistentVolume':
        requested_access_modes = details.get('access_modes') or []
        requested_capacity = None
        reported_capacity = _formatted_size(item.capacity)
        requested_access_modes_label = storage_list_presentation(
            requested_access_modes,
            evidence_reported=specification_reported,
        )
        reported_access_modes_label = 'Not Applicable'
    else:
        requested_capacity = None
        reported_capacity = None
        requested_access_modes_label = 'Not Applicable'
        reported_access_modes_label = 'Not Applicable'

    if item.storage_type == 'StorageClass':
        reclaim_policy = _text(details.get('reclaim_policy'), STORAGE_NOT_REPORTED)
        binding_mode = _text(details.get('volume_binding_mode'), STORAGE_NOT_REPORTED)
        provisioner = _text(details.get('provisioner'), STORAGE_NOT_REPORTED)
        volume_source = 'Not Applicable'
        volume_mode = 'Not Applicable'
    elif item.storage_type == 'PersistentVolume':
        reclaim_policy = _text(
            details.get('reclaim_policy'),
            STORAGE_NOT_CONFIGURED if specification_reported else STORAGE_NOT_REPORTED,
        )
        binding_mode = 'Not Applicable'
        provisioner = 'Not Applicable'
        volume_source = _text(source.get('type'), STORAGE_NOT_REPORTED)
        volume_mode = _text(
            details.get('volume_mode'),
            STORAGE_NOT_CONFIGURED if specification_reported else STORAGE_NOT_REPORTED,
        )
    else:
        reclaim_policy = 'Not Applicable'
        binding_mode = 'Not Applicable'
        provisioner = 'Not Applicable'
        volume_source = 'Not Applicable'
        volume_mode = _text(
            details.get('volume_mode'),
            STORAGE_NOT_CONFIGURED if specification_reported else STORAGE_NOT_REPORTED,
        )
    return {
        'status': lifecycle,
        'cluster': cluster_name,
        'environment': _text(environment, 'Not Reported'),
        'namespace': namespace,
        'name': item.name,
        'resource_type': item.storage_type,
        'storage_class': storage_class_label,
        'requested_capacity': requested_capacity,
        'reported_capacity': reported_capacity,
        'requested_access_modes': requested_access_modes_label,
        'reported_access_modes': reported_access_modes_label,
        'volume_mode': volume_mode,
        'binding_reference': storage_binding_reference(item.storage_type, details),
        'reclaim_policy': reclaim_policy,
        'binding_mode': binding_mode,
        'volume_expansion': storage_expansion_presentation(item.storage_type, details),
        'provisioner': provisioner,
        'volume_source': volume_source,
        'specification_evidence': 'Reported' if specification_reported else STORAGE_NOT_REPORTED,
        'status_evidence': (
            'Not Applicable'
            if item.storage_type == 'StorageClass'
            else ('Reported' if status_reported else STORAGE_NOT_REPORTED)
        ),
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
        'secret_type': (_text(item.secret_type, 'Opaque') if item.object_type == 'Secret' else 'Not Applicable'),
        'key_count': len(item.key_names or []),
        'key_names': item.key_names or [],
        'immutable': item.immutable,
        'metadata_boundary': 'Key Names Only',
        'value_persistence': 'None',
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
        'status_builder': lambda item: ingress_publication_presentation(item.details or {})['label'],
        'type_builder': lambda item: ingress_class_presentation(
            item.ingress_class,
            (item.details or {}).get('ingress_class_source'),
        )[0],
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
        'status_builder': lambda item: storage_lifecycle_presentation(
            item.storage_type, item.status, item.details or {}
        )[0],
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
        category_collected_at = _latest_collected_at(item for item, _cluster_name, _environment in results)
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
            'by_cluster': [{'cluster': label, 'assets': count} for label, count in sorted(by_cluster.items())],
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
            row_builder(item, cluster_name, cluster_environment) for item, cluster_name, cluster_environment in results
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
                'by_cluster': [{'cluster': label, 'assets': count} for label, count in sorted(cluster_counts.items())],
                'by_status': [{'status': label, 'assets': count} for label, count in sorted(status_counts.items())],
                'by_type': [{'resource_type': label, 'assets': count} for label, count in sorted(type_counts.items())],
            },
            'inventory_assets': rows,
            'collected_at': collected_at,
            'generated_at': datetime.now(UTC),
        }
    except Exception as exc:
        return {'_error': str(exc)}
