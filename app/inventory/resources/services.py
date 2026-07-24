from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import (
    _pod_summary,
    _selector_matches,
    _service_port_rows,
    _split_inventory_values,
    format_age,
)
from app.inventory.resources.descriptions import SERVICE_TYPE_DESCRIPTIONS
from app.models import Cluster, PodInventory, ServiceInventory


def get_service_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(ServiceInventory.namespace)
    query = filter_current_generation(query, ServiceInventory)
    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)

    rows = query.distinct().order_by(ServiceInventory.namespace).all()
    return [row[0] for row in rows if row[0]]


def get_service_filter_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(ServiceInventory.service_type)
    query = filter_current_generation(query, ServiceInventory)

    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ServiceInventory.namespace == namespace)

    rows = query.distinct().order_by(ServiceInventory.service_type).all()
    types = [row[0] for row in rows if row[0]]

    headless_query = db.session.query(
        ServiceInventory.id,
    ).filter(
        ServiceInventory.service_type == 'ClusterIP',
        ServiceInventory.cluster_ip == 'None',
    )
    headless_query = filter_current_generation(headless_query, ServiceInventory)
    if cluster_id:
        headless_query = headless_query.filter(
            ServiceInventory.cluster_id == cluster_id,
        )
    if namespace:
        headless_query = headless_query.filter(
            ServiceInventory.namespace == namespace,
        )

    if headless_query.first() is not None and 'Headless' not in types:
        types.append('Headless')

    return sorted(types)


def get_service_inventory(
    cluster_id=None,
    namespace=None,
    service_type=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = db.session.query(
        ServiceInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == ServiceInventory.cluster_id)
    query = filter_current_generation(query, ServiceInventory)

    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ServiceInventory.namespace == namespace)
    if service_type:
        if service_type == 'Headless':
            query = query.filter(
                ServiceInventory.service_type == 'ClusterIP',
                ServiceInventory.cluster_ip == 'None',
            )
        elif service_type == 'ClusterIP':
            query = query.filter(
                ServiceInventory.service_type == 'ClusterIP',
                ServiceInventory.cluster_ip != 'None',
            )
        else:
            query = query.filter(ServiceInventory.service_type == service_type)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                ServiceInventory.service_name.ilike(pattern),
                ServiceInventory.cluster_ip.ilike(pattern),
                ServiceInventory.external_ip.ilike(pattern),
                ServiceInventory.ports.ilike(pattern),
            )
        )

    summary_rows = query.with_entities(
        ServiceInventory.service_type,
        ServiceInventory.cluster_ip,
    ).all()
    services, pagination = paginate_query(
        query.order_by(
            Cluster.name,
            ServiceInventory.namespace,
            ServiceInventory.service_name,
        ),
        page=page,
        per_page=per_page,
    )

    service_types: dict[str, int] = {}
    for raw_type, cluster_ip in summary_rows:
        normalized_type = raw_type or 'Unknown'
        effective_type = 'Headless' if normalized_type == 'ClusterIP' and cluster_ip == 'None' else normalized_type
        service_types[effective_type] = service_types.get(effective_type, 0) + 1

    services_data: list[dict[str, Any]] = []
    for service, cluster_name in services:
        raw_type = service.service_type or 'Unknown'
        effective_type = 'Headless' if raw_type == 'ClusterIP' and service.cluster_ip == 'None' else raw_type
        details = service.details or {}
        endpoints = details.get('endpoints') or {}
        ready_endpoint_count = len(endpoints.get('ready_addresses') or [])
        not_ready_endpoint_count = len(endpoints.get('not_ready_addresses') or [])
        port_rows = _service_port_rows(service)
        port_summary = '-'
        if port_rows:
            first = port_rows[0]
            port_summary = f'{first["port"]}/{first["protocol"]}'
            if len(port_rows) > 1:
                port_summary = f'{port_summary} +{len(port_rows) - 1}'

        external_addresses = _split_inventory_values(service.external_ip)
        services_data.append(
            {
                'id': service.id,
                'cluster_name': cluster_name,
                'namespace': service.namespace,
                'service_name': service.service_name,
                'service_type': effective_type,
                'cluster_ip': service.cluster_ip or '-',
                'external_address': external_addresses[0] if external_addresses else '-',
                'external_address_count': len(external_addresses),
                'port_count': len(port_rows),
                'port_summary': port_summary,
                'endpoint_count': ready_endpoint_count,
                'not_ready_endpoint_count': not_ready_endpoint_count,
                'endpoints_reported': bool(endpoints.get('reported')),
                'created_at': service.created_at,
                'collected_at': service.collected_at,
            }
        )

    return {
        'total_services': pagination['total_items'],
        'cluster_ip': service_types.get('ClusterIP', 0),
        'node_port': service_types.get('NodePort', 0),
        'load_balancer': service_types.get('LoadBalancer', 0),
        'external_name': service_types.get('ExternalName', 0),
        'headless': service_types.get('Headless', 0),
        'service_types': service_types,
        'services': services_data,
        'pagination': pagination,
    }


def get_service_detail(service_id: int) -> dict[str, Any] | None:
    query = db.session.query(
        ServiceInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == ServiceInventory.cluster_id)
    query = filter_current_generation(query, ServiceInventory)
    result = query.filter(ServiceInventory.id == service_id).first()

    if result is None:
        return None

    service, cluster_name = result
    service_type = service.service_type or 'Unknown'
    selector = service.selector or {}
    details = dict(service.details or {})
    endpoints = dict(details.get('endpoints') or {})
    ready_endpoints = [item for item in endpoints.get('ready_addresses') or [] if isinstance(item, dict)]
    not_ready_endpoints = [item for item in endpoints.get('not_ready_addresses') or [] if isinstance(item, dict)]

    pod_query = filter_current_generation(PodInventory.query, PodInventory)
    candidate_pods = (
        pod_query.filter_by(
            cluster_id=service.cluster_id,
            namespace=service.namespace,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )
    matched_pods = [pod for pod in candidate_pods if _selector_matches(selector, pod.labels or {})]

    effective_type = 'Headless' if service_type == 'ClusterIP' and service.cluster_ip == 'None' else service_type
    ports = _service_port_rows(service)
    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}
    cluster_ips = details.get('cluster_ips') or []
    if not cluster_ips and service.cluster_ip:
        cluster_ips = [service.cluster_ip]

    return {
        'id': service.id,
        'cluster_name': cluster_name,
        'namespace': service.namespace,
        'name': service.service_name,
        'type': effective_type,
        'type_description': SERVICE_TYPE_DESCRIPTIONS.get(
            effective_type,
            'Exposes a stable network endpoint for an application or external destination.',
        ),
        'uid': details.get('uid') or '-',
        'generation': int(details.get('generation') or 0),
        'cluster_ip': service.cluster_ip or '-',
        'cluster_ips': cluster_ips,
        'external_ips': _split_inventory_values(service.external_ip),
        'external_name': details.get('external_name') or '-',
        'ip_families': details.get('ip_families') or [],
        'ip_family_policy': details.get('ip_family_policy') or '-',
        'session_affinity': details.get('session_affinity') or 'None',
        'internal_traffic_policy': details.get('internal_traffic_policy') or '-',
        'external_traffic_policy': details.get('external_traffic_policy') or '-',
        'publish_not_ready_addresses': bool(details.get('publish_not_ready_addresses')),
        'health_check_node_port': int(details.get('health_check_node_port') or 0),
        'load_balancer_class': details.get('load_balancer_class') or '-',
        'allocate_load_balancer_node_ports': details.get('allocate_load_balancer_node_ports'),
        'ports': ports,
        'port_count': len(ports),
        'selector': selector,
        'selectors': [f'{key}={value}' for key, value in sorted(selector.items())],
        'age': format_age(service.created_at),
        'created_at': service.created_at,
        'collected_at': service.collected_at,
        'pod_count': len(matched_pods),
        'pods': [_pod_summary(pod) for pod in matched_pods[:8]],
        'pods_truncated': len(matched_pods) > 8,
        'has_selector': bool(selector),
        'endpoints_reported': bool(endpoints.get('reported')),
        'ready_endpoint_count': len(ready_endpoints),
        'not_ready_endpoint_count': len(not_ready_endpoints),
        'endpoints': ready_endpoints[:12],
        'not_ready_endpoints': not_ready_endpoints[:12],
        'endpoints_truncated': len(ready_endpoints) > 12 or len(not_ready_endpoints) > 12,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
    }
