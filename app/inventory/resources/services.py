from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.extensions import db
from app.inventory.resources.common import (
    _pod_summary,
    _selector_matches,
    _service_port_rows,
    _split_inventory_values,
    format_age,
)
from app.inventory.resources.descriptions import SERVICE_TYPE_DESCRIPTIONS
from app.models import Cluster, PodInventory, ServiceInventory


def get_service_filter_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(ServiceInventory.service_type)

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
):
    query = db.session.query(
        ServiceInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == ServiceInventory.cluster_id)

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

    services = query.order_by(
        Cluster.name,
        ServiceInventory.namespace,
        ServiceInventory.service_name,
    ).all()

    namespace_query = db.session.query(ServiceInventory.namespace).distinct()
    if cluster_id:
        namespace_query = namespace_query.filter(ServiceInventory.cluster_id == cluster_id)
    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    services_data: list[dict[str, Any]] = []
    cluster_ip_count = 0
    node_port_count = 0
    load_balancer_count = 0
    external_name_count = 0
    headless_count = 0
    service_types: dict[str, int] = {}

    for service, cluster_name in services:
        raw_type = service.service_type or 'Unknown'
        effective_type = 'Headless' if raw_type == 'ClusterIP' and service.cluster_ip == 'None' else raw_type
        service_types[effective_type] = service_types.get(effective_type, 0) + 1

        if effective_type == 'ClusterIP':
            cluster_ip_count += 1
        elif effective_type == 'NodePort':
            node_port_count += 1
        elif effective_type == 'LoadBalancer':
            load_balancer_count += 1
        elif effective_type == 'ExternalName':
            external_name_count += 1
        elif effective_type == 'Headless':
            headless_count += 1

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
        'total_services': len(services),
        'cluster_ip': cluster_ip_count,
        'node_port': node_port_count,
        'load_balancer': load_balancer_count,
        'external_name': external_name_count,
        'headless': headless_count,
        'namespaces': namespaces,
        'service_filter_types': get_service_filter_types(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'service_types': service_types,
        'services': services_data,
    }


def get_service_detail(service_id: int) -> dict[str, Any] | None:
    result = (
        db.session.query(
            ServiceInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == ServiceInventory.cluster_id)
        .filter(ServiceInventory.id == service_id)
        .first()
    )

    if result is None:
        return None

    service, cluster_name = result
    service_type = service.service_type or 'Unknown'
    selector = service.selector or {}
    details = dict(service.details or {})
    endpoints = dict(details.get('endpoints') or {})
    ready_endpoints = [item for item in endpoints.get('ready_addresses') or [] if isinstance(item, dict)]
    not_ready_endpoints = [item for item in endpoints.get('not_ready_addresses') or [] if isinstance(item, dict)]

    candidate_pods = (
        PodInventory.query.filter_by(
            cluster_id=service.cluster_id,
            namespace=service.namespace,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )
    matched_pods = [pod for pod in candidate_pods if _selector_matches(selector, pod.labels or {})]

    effective_type = 'Headless' if service_type == 'ClusterIP' and service.cluster_ip == 'None' else service_type
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
        'ports': _service_port_rows(service),
        'port_count': len(_service_port_rows(service)),
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


