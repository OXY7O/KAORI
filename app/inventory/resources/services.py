from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import (
    _pod_summary,
    _selector_matches,
    _service_port_rows,
    format_age,
)
from app.inventory.resources.descriptions import SERVICE_TYPE_DESCRIPTIONS
from app.inventory.resources.pod_semantics import pod_operational_state
from app.inventory.resources.service_semantics import (
    access_model,
    access_presentation,
    backend_registration,
    effective_service_type,
    operational_context,
    port_mapping,
)
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
    values = {
        effective_service_type(raw_type, cluster_ip)
        for raw_type, cluster_ip in query.distinct().all()
    }
    return sorted(values)


def _apply_filters(query, cluster_id=None, namespace=None, service_type=None, search=None):
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
        elif service_type == 'Unknown':
            query = query.filter(
                or_(
                    ServiceInventory.service_type.is_(None),
                    func.trim(ServiceInventory.service_type) == '',
                )
            )
        else:
            query = query.filter(ServiceInventory.service_type == service_type)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                ServiceInventory.service_name.ilike(pattern),
                ServiceInventory.namespace.ilike(pattern),
                ServiceInventory.service_type.ilike(pattern),
                ServiceInventory.cluster_ip.ilike(pattern),
                cast(ServiceInventory.details, String).ilike(pattern),
            )
        )
    return query


def _service_summary_rows(cluster_id=None, namespace=None, service_type=None, search=None):
    query = db.session.query(
        ServiceInventory.service_type,
        ServiceInventory.cluster_ip,
        ServiceInventory.selector,
        ServiceInventory.details,
    )
    query = filter_current_generation(query, ServiceInventory)
    return _apply_filters(query, cluster_id, namespace, service_type, search).all()


def _service_summary(summary_rows) -> dict[str, Any]:
    type_counts: dict[str, int] = {}
    registration_counts = {'registered': 0, 'exceptions': 0, 'not_reported': 0}
    for raw_type, cluster_ip, selector, details in summary_rows:
        effective = effective_service_type(raw_type, cluster_ip)
        type_counts[effective] = type_counts.get(effective, 0) + 1
        registration = backend_registration(
            effective,
            selector or {},
            (details or {}).get('endpoints') or {},
        )
        if registration['ready'] > 0 and not registration['exception']:
            registration_counts['registered'] += 1
        if registration['exception']:
            registration_counts['exceptions'] += 1
        if registration['label'] == 'Not Reported':
            registration_counts['not_reported'] += 1
    return {'type_counts': type_counts, 'registration_counts': registration_counts}


def _service_access_details(service: ServiceInventory, effective_type: str) -> tuple[str, str]:
    details = service.details or {}
    cluster_ips = list(details.get('cluster_ips') or ([service.cluster_ip] if service.cluster_ip else []))
    external_addresses = list(details.get('external_addresses') or [])
    return access_presentation(
        effective_type,
        cluster_ips,
        external_addresses,
        details.get('external_name'),
    )


def _present_service_row(service: ServiceInventory, cluster_name: str, cluster_environment: str) -> dict[str, Any]:
    effective = effective_service_type(service.service_type, service.cluster_ip)
    details = service.details or {}
    registration = backend_registration(
        effective,
        service.selector or {},
        details.get('endpoints') or {},
    )
    ports = _service_port_rows(service)
    mapping, port_supporting = port_mapping(ports)
    access_address, access_supporting = _service_access_details(service, effective)
    return {
        'id': service.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'namespace': service.namespace,
        'service_name': service.service_name,
        'service_type': effective,
        'access_model': access_model(effective),
        'access_address': access_address,
        'access_supporting': access_supporting,
        'port_mapping': mapping,
        'port_supporting': port_supporting,
        'backend': registration,
        'created_at': service.created_at,
        'collected_at': service.collected_at,
    }


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

    services, pagination = paginate_query(
        query.order_by(Cluster.name, ServiceInventory.namespace, ServiceInventory.service_name),
        page=page,
        per_page=per_page,
    )
    summary = _service_summary(
        _service_summary_rows(cluster_id, namespace, service_type, search)
    )
    type_counts = summary['type_counts']
    registration_counts = summary['registration_counts']
    rows = [
        _present_service_row(service, cluster_name, cluster_environment)
        for service, cluster_name, cluster_environment in services
    ]

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
        'unknown_type': type_counts.get('Unknown', 0),
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


def _present_selected_pods(pods: list[PodInventory]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pod in pods:
        row = _pod_summary(pod)
        state, tone, evidence = pod_operational_state(pod.phase, pod.ready)
        details = pod.details or {}
        specification_reported = details.get('specification_evidence_reported', True)
        container_count = len(pod.container_names or []) if specification_reported else None
        age = format_age(pod.created_at)
        age_display = age if age != '-' else 'Not Reported'
        row.update(
            {
                'status': state,
                'status_tone': tone,
                'supporting_primary': f'Node {pod.node_name or "Not Scheduled"} · {evidence}',
                'supporting_secondary': (
                    f'{container_count} Containers · Age {age_display}'
                    if container_count is not None
                    else f'Container evidence not reported · Age {age_display}'
                ),
            }
        )
        rows.append(row)
    return rows


def _endpoint_resource(item: dict[str, Any], registration: dict[str, Any], state: str) -> dict[str, Any]:
    terminating = item.get('terminating') is True
    serving = item.get('serving')
    condition_parts = []
    if serving is not None:
        condition_parts.append(f'Serving {"Yes" if serving else "No"}')
    if terminating:
        condition_parts.append('Terminating')
    condition_context = ' · '.join(condition_parts) or registration['source']
    return {
        'name': item.get('ip') or item.get('hostname') or 'Endpoint Address',
        'supporting_primary': f"{item.get('target_kind') or 'Target'} · {item.get('target_name') or 'Not Reported'}",
        'supporting_secondary': f"Node {item.get('node_name') or 'Not Reported'} · {condition_context}",
        'status': state,
        'status_tone': 'normal' if state == 'Ready' and not terminating else 'warning',
    }


def _present_endpoint_resources(endpoint_evidence: dict[str, Any], registration: dict[str, Any]):
    ready = [item for item in endpoint_evidence.get('ready_addresses') or [] if isinstance(item, dict)]
    not_ready = [item for item in endpoint_evidence.get('not_ready_addresses') or [] if isinstance(item, dict)]
    resources = [
        *[_endpoint_resource(item, registration, 'Ready') for item in ready[:12]],
        *[_endpoint_resource(item, registration, 'Not Ready') for item in not_ready[:12]],
    ]
    return ready, not_ready, resources



def _service_detail_configuration(
    service: ServiceInventory,
    cluster_name: str,
    details: dict[str, Any],
    effective: str,
) -> dict[str, Any]:
    cluster_ips = list(details.get('cluster_ips') or ([service.cluster_ip] if service.cluster_ip else []))
    external_ips = list(details.get('external_addresses') or [])
    return {
        'id': service.id,
        'cluster_name': cluster_name,
        'cluster_id': service.cluster_id,
        'namespace': service.namespace,
        'name': service.service_name,
        'type': effective,
        'access_model': access_model(effective),
        'type_description': SERVICE_TYPE_DESCRIPTIONS.get(
            effective,
            'Exposes a stable network endpoint for an application or external destination.',
        ),
        'specification_evidence_reported': details.get('specification_evidence_reported', True),
        'uid': details.get('uid') or 'Not Reported',
        'generation': int(details.get('generation') or 0) or 'Not Reported',
        'cluster_ip': 'None (Headless)' if effective == 'Headless' else (service.cluster_ip or 'Not Reported'),
        'cluster_ips': [value for value in cluster_ips if value and value != 'None'],
        'external_ips': external_ips,
        'declared_external_ips': list(details.get('declared_external_ips') or []),
        'load_balancer_addresses': list(details.get('load_balancer_ingress') or []),
        'load_balancer_status_reported': details.get('load_balancer_status_reported'),
        'external_name': details.get('external_name') or 'Not Configured',
        'ip_families': details.get('ip_families') or [],
        'ip_family_policy': details.get('ip_family_policy') or 'Not Reported',
        'session_affinity': details.get('session_affinity') or 'None',
        'internal_traffic_policy': details.get('internal_traffic_policy') or 'Not Reported',
        'external_traffic_policy': details.get('external_traffic_policy') or 'Not Reported',
        'publish_not_ready_addresses': bool(details.get('publish_not_ready_addresses')),
        'health_check_node_port': int(details.get('health_check_node_port') or 0),
        'load_balancer_class': details.get('load_balancer_class') or 'Not Configured',
        'allocate_load_balancer_node_ports': details.get('allocate_load_balancer_node_ports'),
        'age': format_age(service.created_at),
        'created_at': service.created_at,
        'collected_at': service.collected_at,
        'labels': dict(sorted((details.get('labels') or {}).items())),
        'annotations': dict(sorted((details.get('annotations') or {}).items())),
    }


def _service_detail_relationships(
    *,
    selector: dict[str, str],
    effective: str,
    registration: dict[str, Any],
    pod_count: int,
    matched_pods: list[PodInventory],
    ready_endpoints: list[dict[str, Any]],
    not_ready_endpoints: list[dict[str, Any]],
    endpoint_resources: list[dict[str, Any]],
) -> dict[str, Any]:
    endpoint_registration_applicable = effective != 'ExternalName'
    endpoints_reported = registration['reported'] if endpoint_registration_applicable else False
    pod_relationship_applicable = bool(selector)
    return {
        'selector': selector,
        'selector_entries': dict(sorted(selector.items())),
        'selector_applicable': effective != 'ExternalName',
        'pod_relationship_applicable': pod_relationship_applicable,
        'pod_count': pod_count if pod_relationship_applicable else None,
        'pods': _present_selected_pods(matched_pods),
        'pods_truncated': pod_count > len(matched_pods),
        'backend': registration,
        'endpoint_registration_applicable': endpoint_registration_applicable,
        'endpoints_reported': endpoints_reported,
        'endpoint_source': registration['source'],
        'ready_endpoint_count': registration['ready'] if endpoints_reported else None,
        'not_ready_endpoint_count': registration['not_ready'] if endpoints_reported else None,
        'endpoint_resources': endpoint_resources,
        'endpoints_truncated': len(ready_endpoints) > 12 or len(not_ready_endpoints) > 12,
        'operational_context': operational_context(registration),
    }

def get_service_detail(service_id: int) -> dict[str, Any] | None:
    query = db.session.query(ServiceInventory, Cluster.name.label('cluster_name')).join(
        Cluster,
        Cluster.id == ServiceInventory.cluster_id,
    )
    query = filter_current_generation(query, ServiceInventory)
    result = query.filter(ServiceInventory.id == service_id).first()
    if result is None:
        return None

    service, cluster_name = result
    details = dict(service.details or {})
    selector = service.selector or {}
    effective = effective_service_type(service.service_type, service.cluster_ip)
    endpoint_evidence = dict(details.get('endpoints') or {})
    registration = backend_registration(effective, selector, endpoint_evidence)
    ready_endpoints, not_ready_endpoints, endpoint_resources = _present_endpoint_resources(
        endpoint_evidence,
        registration,
    )
    pod_count, matched_pods = _matched_pod_preview(service, selector)
    ports = _service_port_rows(service)
    return {
        **_service_detail_configuration(service, cluster_name, details, effective),
        **_service_detail_relationships(
            selector=selector,
            effective=effective,
            registration=registration,
            pod_count=pod_count,
            matched_pods=matched_pods,
            ready_endpoints=ready_endpoints,
            not_ready_endpoints=not_ready_endpoints,
            endpoint_resources=endpoint_resources,
        ),
        'ports': ports,
        'port_count': len(ports),
    }
