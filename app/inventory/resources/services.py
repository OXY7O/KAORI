from __future__ import annotations

from typing import Any

from sqlalchemy import cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB

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


def get_service_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(ServiceInventory.namespace)
    query = filter_current_generation(query, ServiceInventory)
    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(ServiceInventory.namespace).all()
    return [row[0] for row in rows if row[0]]


def get_service_filter_types(cluster_id: str | None = None, namespace: str | None = None) -> list[str]:
    query = db.session.query(ServiceInventory.service_type, ServiceInventory.cluster_ip)
    query = filter_current_generation(query, ServiceInventory)
    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ServiceInventory.namespace == namespace)
    rows = query.distinct().all()
    values = {
        'Headless' if raw_type == 'ClusterIP' and cluster_ip == 'None' else (raw_type or 'Unknown')
        for raw_type, cluster_ip in rows
    }
    return sorted(values)


def _effective_type(service_type: str | None, cluster_ip: str | None) -> str:
    raw_type = service_type or 'Unknown'
    return 'Headless' if raw_type == 'ClusterIP' and cluster_ip == 'None' else raw_type


def _backend_registration(
    service_type: str,
    selector: dict[str, str],
    endpoints: dict[str, Any],
) -> dict[str, Any]:
    ready = len(endpoints.get('ready_addresses') or [])
    not_ready = len(endpoints.get('not_ready_addresses') or [])
    reported = bool(endpoints.get('reported'))
    source = str(endpoints.get('source') or 'Endpoint Evidence')

    if service_type == 'ExternalName':
        return {
            'label': 'External Destination',
            'tone': 'info',
            'supporting': 'DNS destination',
            'ready': ready,
            'not_ready': not_ready,
            'reported': reported,
            'source': source,
            'exception': False,
        }
    if not selector:
        return {
            'label': 'Manually Managed',
            'tone': 'info',
            'supporting': f'{ready + not_ready} registered addresses' if reported else 'Selectorless Service',
            'ready': ready,
            'not_ready': not_ready,
            'reported': reported,
            'source': source,
            'exception': False,
        }
    if not reported:
        return {
            'label': 'Not Reported',
            'tone': 'unknown',
            'supporting': 'Endpoint evidence unavailable',
            'ready': ready,
            'not_ready': not_ready,
            'reported': False,
            'source': source,
            'exception': True,
        }
    if ready > 0 and not_ready == 0:
        return {
            'label': 'Registered',
            'tone': 'normal',
            'supporting': f'{ready} ready',
            'ready': ready,
            'not_ready': not_ready,
            'reported': True,
            'source': source,
            'exception': False,
        }
    if ready > 0 and not_ready > 0:
        return {
            'label': 'Partial',
            'tone': 'warning',
            'supporting': f'{ready} ready · {not_ready} not ready',
            'ready': ready,
            'not_ready': not_ready,
            'reported': True,
            'source': source,
            'exception': True,
        }
    if not_ready > 0:
        return {
            'label': 'Not Ready',
            'tone': 'critical',
            'supporting': f'{not_ready} not ready',
            'ready': ready,
            'not_ready': not_ready,
            'reported': True,
            'source': source,
            'exception': True,
        }
    return {
        'label': 'No Registered Backends',
        'tone': 'warning',
        'supporting': '0 registered addresses',
        'ready': 0,
        'not_ready': 0,
        'reported': True,
        'source': source,
        'exception': True,
    }


def _access_model(service_type: str) -> str:
    return {
        'ClusterIP': 'Cluster Internal',
        'Headless': 'Direct Pod Discovery',
        'NodePort': 'Node Port Publication',
        'LoadBalancer': 'Load Balancer Publication',
        'ExternalName': 'External DNS Alias',
    }.get(service_type, service_type)


def _port_mapping(port_rows: list[dict[str, Any]]) -> tuple[str, str]:
    if not port_rows:
        return 'No Ports', 'No port mapping reported'
    first = port_rows[0]
    target = first.get('target_port') or '-'
    primary = f'{first.get("port", 0)}/{first.get("protocol", "TCP")} → {target}'
    supporting = f'{len(port_rows)} ' + ('Port' if len(port_rows) == 1 else 'Ports')
    return primary, supporting


def _pod_operational_state(phase: str | None, ready: str | None) -> tuple[str, str]:
    phase_value = (phase or '').strip()
    ready_value = (ready or '').strip()
    ready_all = False
    if '/' in ready_value:
        numerator, denominator = ready_value.split('/', 1)
        ready_all = numerator.isdigit() and denominator.isdigit() and int(denominator) > 0 and numerator == denominator
    if phase_value == 'Failed':
        return 'Failed', 'critical'
    if phase_value == 'Succeeded':
        return 'Completed', 'info'
    if phase_value == 'Pending':
        return 'Starting', 'pending'
    if phase_value == 'Running' and ready_all:
        return 'Ready', 'normal'
    if phase_value == 'Running':
        return 'Not Ready', 'warning'
    return 'Unknown', 'unknown'


def _apply_filters(query, cluster_id=None, namespace=None, service_type=None, search=None):
    if cluster_id:
        query = query.filter(ServiceInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ServiceInventory.namespace == namespace)
    if service_type:
        if service_type == 'Headless':
            query = query.filter(ServiceInventory.service_type == 'ClusterIP', ServiceInventory.cluster_ip == 'None')
        elif service_type == 'ClusterIP':
            query = query.filter(ServiceInventory.service_type == 'ClusterIP', ServiceInventory.cluster_ip != 'None')
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
    return query


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
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == ServiceInventory.cluster_id)
    query = filter_current_generation(query, ServiceInventory)
    query = _apply_filters(query, cluster_id, namespace, service_type, search)

    summary_query = db.session.query(
        ServiceInventory.service_type,
        ServiceInventory.cluster_ip,
        ServiceInventory.selector,
        ServiceInventory.details,
    )
    summary_query = filter_current_generation(summary_query, ServiceInventory)
    summary_query = _apply_filters(summary_query, cluster_id, namespace, service_type, search)
    summary_rows = summary_query.all()

    services, pagination = paginate_query(
        query.order_by(Cluster.name, ServiceInventory.namespace, ServiceInventory.service_name),
        page=page,
        per_page=per_page,
    )

    type_counts: dict[str, int] = {}
    registration_counts = {
        'registered': 0,
        'exceptions': 0,
        'not_reported': 0,
    }
    for raw_type, cluster_ip, selector, details in summary_rows:
        effective = _effective_type(raw_type, cluster_ip)
        type_counts[effective] = type_counts.get(effective, 0) + 1
        registration = _backend_registration(effective, selector or {}, (details or {}).get('endpoints') or {})
        if registration['label'] == 'Registered':
            registration_counts['registered'] += 1
        if registration['exception']:
            registration_counts['exceptions'] += 1
        if registration['label'] == 'Not Reported':
            registration_counts['not_reported'] += 1

    rows: list[dict[str, Any]] = []
    for service, cluster_name, cluster_environment in services:
        effective = _effective_type(service.service_type, service.cluster_ip)
        details = service.details or {}
        endpoint_evidence = details.get('endpoints') or {}
        registration = _backend_registration(effective, service.selector or {}, endpoint_evidence)
        ports = _service_port_rows(service)
        port_mapping, port_supporting = _port_mapping(ports)
        external_addresses = _split_inventory_values(service.external_ip)
        cluster_ips = details.get('cluster_ips') or ([service.cluster_ip] if service.cluster_ip else [])
        access_addresses = [value for value in [*cluster_ips, *external_addresses] if value and value != '-']
        rows.append(
            {
                'id': service.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': service.namespace,
                'service_name': service.service_name,
                'service_type': effective,
                'access_model': _access_model(effective),
                'access_address': access_addresses[0] if access_addresses else (details.get('external_name') or '-'),
                'address_count': len(access_addresses),
                'port_mapping': port_mapping,
                'port_supporting': port_supporting,
                'backend': registration,
                'age': format_age(service.created_at),
                'created_at': service.created_at,
                'collected_at': service.collected_at,
            }
        )

    total = pagination['total_items']
    exceptions = registration_counts['exceptions']
    posture_label = 'No Data' if total == 0 else ('Attention' if exceptions else 'Stable')
    posture_tone = 'unknown' if total == 0 else ('warning' if exceptions else 'normal')
    return {
        'total_services': total,
        'cluster_ip': type_counts.get('ClusterIP', 0),
        'node_port': type_counts.get('NodePort', 0),
        'load_balancer': type_counts.get('LoadBalancer', 0),
        'external_name': type_counts.get('ExternalName', 0),
        'headless': type_counts.get('Headless', 0),
        'access_model_count': len(type_counts),
        'registered_backends': registration_counts['registered'],
        'backend_exceptions': exceptions,
        'endpoint_evidence_missing': registration_counts['not_reported'],
        'overall_posture_label': posture_label,
        'overall_posture_tone': posture_tone,
        'services': rows,
        'pagination': pagination,
    }


def _matched_pod_preview(service: ServiceInventory, selector: dict[str, str]) -> tuple[int, list[PodInventory]]:
    if not selector:
        return 0, []
    pod_query = filter_current_generation(PodInventory.query, PodInventory).filter_by(
        cluster_id=service.cluster_id,
        namespace=service.namespace,
    )
    try:
        dialect = db.session.get_bind().dialect.name
    except Exception:
        dialect = ''
    if dialect == 'postgresql':
        matched_query = pod_query.filter(cast(PodInventory.labels, JSONB).contains(selector))
        return matched_query.count(), matched_query.order_by(PodInventory.pod_name).limit(8).all()
    candidate_pods = pod_query.order_by(PodInventory.pod_name).all()
    matched = [pod for pod in candidate_pods if _selector_matches(selector, pod.labels or {})]
    return len(matched), matched[:8]


def get_service_detail(service_id: int) -> dict[str, Any] | None:
    query = db.session.query(ServiceInventory, Cluster.name.label('cluster_name')).join(
        Cluster, Cluster.id == ServiceInventory.cluster_id
    )
    query = filter_current_generation(query, ServiceInventory)
    result = query.filter(ServiceInventory.id == service_id).first()
    if result is None:
        return None

    service, cluster_name = result
    details = dict(service.details or {})
    selector = service.selector or {}
    effective = _effective_type(service.service_type, service.cluster_ip)
    endpoint_evidence = dict(details.get('endpoints') or {})
    registration = _backend_registration(effective, selector, endpoint_evidence)
    ready_endpoints = [item for item in endpoint_evidence.get('ready_addresses') or [] if isinstance(item, dict)]
    not_ready_endpoints = [item for item in endpoint_evidence.get('not_ready_addresses') or [] if isinstance(item, dict)]
    pod_count, matched_pods = _matched_pod_preview(service, selector)

    pod_rows = []
    for pod in matched_pods:
        row = _pod_summary(pod)
        state, tone = _pod_operational_state(pod.phase, pod.ready)
        row.update(
            {
                'status': state,
                'status_tone': tone,
                'supporting_primary': f'Node {pod.node_name or "Not Scheduled"} · Ready {pod.ready or "-"}',
                'supporting_secondary': f'{len(pod.container_names or [])} Containers · Age {format_age(pod.created_at)}',
            }
        )
        pod_rows.append(row)

    ports = _service_port_rows(service)
    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}
    cluster_ips = details.get('cluster_ips') or ([service.cluster_ip] if service.cluster_ip else [])
    external_ips = _split_inventory_values(service.external_ip)

    endpoint_rows = []
    endpoint_resources = []
    for item in ready_endpoints[:12]:
        endpoint_rows.append({**item, 'state': 'Ready', 'tone': 'normal'})
        endpoint_resources.append({
            'name': item.get('ip') or item.get('hostname') or 'Endpoint Address',
            'supporting_primary': f"{item.get('target_kind') or 'Target'} · {item.get('target_name') or 'Not Reported'}",
            'supporting_secondary': f"Node {item.get('node_name') or 'Not Reported'} · {registration['source']}",
            'status': 'Ready',
            'status_tone': 'normal',
        })
    for item in not_ready_endpoints[:12]:
        endpoint_rows.append({**item, 'state': 'Not Ready', 'tone': 'warning'})
        endpoint_resources.append({
            'name': item.get('ip') or item.get('hostname') or 'Endpoint Address',
            'supporting_primary': f"{item.get('target_kind') or 'Target'} · {item.get('target_name') or 'Not Reported'}",
            'supporting_secondary': f"Node {item.get('node_name') or 'Not Reported'} · {registration['source']}",
            'status': 'Not Ready',
            'status_tone': 'warning',
        })

    if registration['label'] == 'No Registered Backends':
        operational_context = {
            'title': 'Review Service Backend Registration',
            'description': 'No registered backend address is present for this selector-based Service. Confirm selector matching and workload readiness.',
            'icon': 'route-off',
            'tone': 'warning',
        }
    elif registration['label'] == 'Partial':
        operational_context = {
            'title': 'Investigate Not-Ready Endpoints',
            'description': 'Ready and not-ready backend addresses are both present. Review selected Pod readiness and endpoint conditions.',
            'icon': 'triangle-alert',
            'tone': 'warning',
        }
    elif registration['label'] == 'Not Ready':
        operational_context = {
            'title': 'Restore Backend Readiness',
            'description': 'All reported backend addresses are not ready. Review selected Pods and endpoint conditions before relying on this Service.',
            'icon': 'shield-alert',
            'tone': 'critical',
        }
    elif registration['label'] == 'Not Reported':
        operational_context = {
            'title': 'Refresh Endpoint Evidence',
            'description': 'Endpoint registration evidence was not reported. Run inventory sync before drawing backend readiness conclusions.',
            'icon': 'refresh-cw',
            'tone': 'unknown',
        }
    elif registration['label'] == 'External Destination':
        operational_context = {
            'title': 'Review External Destination',
            'description': 'This ExternalName Service delegates resolution to an external DNS destination. Inventory does not validate destination reachability.',
            'icon': 'external-link',
            'tone': 'info',
        }
    else:
        operational_context = {
            'title': 'Service Snapshot Ready for Review',
            'description': 'Backend registration evidence is available in the committed snapshot. Traffic health and reachability remain outside inventory scope.',
            'icon': 'circle-check',
            'tone': 'normal',
        }

    return {
        'id': service.id,
        'cluster_name': cluster_name,
        'cluster_id': service.cluster_id,
        'namespace': service.namespace,
        'name': service.service_name,
        'type': effective,
        'access_model': _access_model(effective),
        'type_description': SERVICE_TYPE_DESCRIPTIONS.get(
            effective, 'Exposes a stable network endpoint for an application or external destination.'
        ),
        'uid': details.get('uid') or '-',
        'generation': int(details.get('generation') or 0),
        'cluster_ip': service.cluster_ip or '-',
        'cluster_ips': cluster_ips,
        'external_ips': external_ips,
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
        'selector_entries': dict(sorted(selector.items())),
        'age': format_age(service.created_at),
        'created_at': service.created_at,
        'collected_at': service.collected_at,
        'pod_count': pod_count,
        'pods': pod_rows,
        'pods_truncated': pod_count > len(pod_rows),
        'has_selector': bool(selector),
        'backend': registration,
        'endpoint_source': registration['source'],
        'ready_endpoint_count': registration['ready'],
        'not_ready_endpoint_count': registration['not_ready'],
        'endpoint_rows': endpoint_rows,
        'endpoint_resources': endpoint_resources,
        'endpoints_truncated': len(ready_endpoints) > 12 or len(not_ready_endpoints) > 12,
        'labels': dict(sorted(labels.items())),
        'annotations': dict(sorted(annotations.items())),
        'operational_context': operational_context,
    }
