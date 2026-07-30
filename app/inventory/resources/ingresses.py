from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import _split_inventory_values, format_age
from app.models import Cluster, IngressInventory, ServiceInventory


def get_ingress_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(IngressInventory.namespace)
    query = filter_current_generation(query, IngressInventory)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(IngressInventory.namespace).all()
    return [row[0] for row in rows if row[0]]


def get_ingress_filter_classes(cluster_id: str | None = None, namespace: str | None = None) -> list[str]:
    query = db.session.query(IngressInventory.ingress_class)
    query = filter_current_generation(query, IngressInventory)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)
    rows = query.distinct().order_by(IngressInventory.ingress_class).all()
    return [row[0] for row in rows if row[0]]


def _ingress_hosts(host: str | None, details: dict[str, Any]) -> list[str]:
    hosts = [str(value) for value in (details.get('hosts') or []) if value and value != '-']
    if not hosts and host and host != '-':
        hosts.append(host)
    return list(dict.fromkeys(hosts))


def _ingress_addresses(address: str | None) -> list[str]:
    values = _split_inventory_values(address)
    if values:
        return values
    return []


def _ingress_tls_secret_count(tls_entries: list[Any]) -> int:
    return len(
        {
            item.get('secret_name')
            for item in tls_entries
            if isinstance(item, dict) and item.get('secret_name') not in (None, '', '-')
        }
    )


def _apply_filters(query, cluster_id=None, namespace=None, ingress_class=None, tls_status=None, search=None):
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)
    if ingress_class:
        query = query.filter(IngressInventory.ingress_class == ingress_class)
    if tls_status == 'enabled':
        query = query.filter(IngressInventory.tls_enabled.is_(True))
    elif tls_status == 'disabled':
        query = query.filter(IngressInventory.tls_enabled.is_(False))
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                IngressInventory.ingress_name.ilike(pattern),
                IngressInventory.host.ilike(pattern),
                IngressInventory.address.ilike(pattern),
                IngressInventory.ingress_class.ilike(pattern),
            )
        )
    return query


def _route_service_names(paths: list[Any]) -> set[str]:
    return {
        str(item.get('service_name'))
        for item in paths
        if isinstance(item, dict) and item.get('service_name') not in (None, '', '-')
    }


def get_ingress_inventory(
    cluster_id=None,
    namespace=None,
    ingress_class=None,
    tls_status=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = db.session.query(
        IngressInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == IngressInventory.cluster_id)
    query = filter_current_generation(query, IngressInventory)
    query = _apply_filters(query, cluster_id, namespace, ingress_class, tls_status, search)

    summary_query = db.session.query(
        IngressInventory.tls_enabled,
        IngressInventory.host,
        IngressInventory.address,
        IngressInventory.ingress_class,
        IngressInventory.backend_paths,
        IngressInventory.details,
    )
    summary_query = filter_current_generation(summary_query, IngressInventory)
    summary_query = _apply_filters(summary_query, cluster_id, namespace, ingress_class, tls_status, search)
    summary_rows = summary_query.all()

    ingresses, pagination = paginate_query(
        query.order_by(Cluster.name, IngressInventory.namespace, IngressInventory.ingress_name),
        page=page,
        per_page=per_page,
    )

    hosts: set[str] = set()
    classes: set[str] = set()
    backend_services: set[str] = set()
    tls_reference_count = 0
    backend_route_count = 0
    missing_addresses = 0
    routing_exceptions = 0
    for tls_enabled, host, address, class_name, backend_paths, details in summary_rows:
        hosts.update(_ingress_hosts(host, details or {}))
        if class_name:
            classes.add(class_name)
        paths = [item for item in (backend_paths or []) if isinstance(item, dict)]
        backend_services.update(_route_service_names(paths))
        backend_route_count += len(paths)
        tls_reference_count += int(bool(tls_enabled))
        if not _ingress_addresses(address):
            missing_addresses += 1
        if not paths:
            routing_exceptions += 1

    ingress_data: list[dict[str, Any]] = []
    for ingress, cluster_name, cluster_environment in ingresses:
        details = ingress.details or {}
        ingress_hosts = _ingress_hosts(ingress.host, details)
        addresses = _ingress_addresses(ingress.address)
        paths = [item for item in (ingress.backend_paths or []) if isinstance(item, dict)]
        service_names = _route_service_names(paths)
        ingress_data.append(
            {
                'id': ingress.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': ingress.namespace,
                'name': ingress.ingress_name,
                'class': ingress.ingress_class or 'Not Reported',
                'host': ingress_hosts[0] if ingress_hosts else 'No Host Declared',
                'host_count': len(ingress_hosts),
                'address': addresses[0] if addresses else 'Not Published',
                'address_count': len(addresses),
                'tls_reference_label': (
                    f'{_ingress_tls_secret_count(details.get("tls") or [])} Secret References'
                    if ingress.tls_enabled
                    else 'No TLS Reference'
                ),
                'tls_host_count': sum(len(item.get('hosts') or []) for item in (details.get('tls') or []) if isinstance(item, dict)),
                'backend_count': len(paths),
                'service_count': len(service_names),
                'routing_label': f'{len(paths)} Paths · {len(service_names)} Services',
                'publication_label': 'Published' if addresses else 'Address Pending',
                'publication_tone': 'normal' if addresses else 'pending',
                'age': format_age(ingress.created_at),
                'created_at': ingress.created_at,
                'collected_at': ingress.collected_at,
            }
        )

    total = pagination['total_items']
    exceptions = missing_addresses + routing_exceptions
    posture_label = 'No Data' if total == 0 else ('Attention' if exceptions else 'Published')
    posture_tone = 'unknown' if total == 0 else ('warning' if exceptions else 'normal')
    return {
        'total_ingresses': total,
        'total_hosts': len(hosts),
        'ingress_classes': len(classes),
        'backend_route_count': backend_route_count,
        'backend_service_count': len(backend_services),
        'tls_references': tls_reference_count,
        'missing_addresses': missing_addresses,
        'routing_exceptions': routing_exceptions,
        'overall_posture_label': posture_label,
        'overall_posture_tone': posture_tone,
        'ingresses': ingress_data,
        'pagination': pagination,
    }


def get_ingress_detail(ingress_id: int) -> dict[str, Any] | None:
    query = db.session.query(IngressInventory, Cluster.name.label('cluster_name')).join(
        Cluster, Cluster.id == IngressInventory.cluster_id
    )
    query = filter_current_generation(query, IngressInventory)
    result = query.filter(IngressInventory.id == ingress_id).first()
    if result is None:
        return None

    ingress, cluster_name = result
    details = dict(ingress.details or {})
    backend_paths = [item for item in (ingress.backend_paths or []) if isinstance(item, dict)]
    hosts = _ingress_hosts(ingress.host, details)
    if not hosts:
        hosts = sorted({str(item.get('host')) for item in backend_paths if item.get('host') not in (None, '', '-')})
    addresses = _ingress_addresses(ingress.address)
    service_names = sorted(_route_service_names(backend_paths))

    service_map: dict[str, ServiceInventory] = {}
    if service_names:
        service_query = filter_current_generation(ServiceInventory.query, ServiceInventory).filter(
            ServiceInventory.cluster_id == ingress.cluster_id,
            ServiceInventory.namespace == ingress.namespace,
            ServiceInventory.service_name.in_(service_names),
        )
        service_map = {item.service_name: item for item in service_query.all()}

    resolved_paths: list[dict[str, Any]] = []
    for item in backend_paths:
        service_name = str(item.get('service_name') or '-')
        if service_name == '-':
            state, tone = 'Not Reported', 'unknown'
        elif service_name in service_map:
            state, tone = 'Resolved', 'normal'
        else:
            state, tone = 'Missing', 'critical'
        resolved_paths.append(
            {
                'host': str(item.get('host') or '-'),
                'path': str(item.get('path') or '/'),
                'path_type': str(item.get('path_type') or '-'),
                'service_name': service_name,
                'service_port': str(item.get('service_port') or '-'),
                'reference_state': state,
                'reference_tone': tone,
            }
        )

    backend_resources = []
    for service_name in service_names:
        resolved = service_map.get(service_name)
        backend_resources.append(
            {
                'name': service_name,
                'supporting_primary': f'Namespace {ingress.namespace}',
                'supporting_secondary': (
                    f'{resolved.service_type or "Service"} · {resolved.cluster_ip or "No Cluster IP"}'
                    if resolved
                    else 'No matching Service in the committed snapshot'
                ),
                'status': 'Resolved' if resolved else 'Missing',
                'status_tone': 'normal' if resolved else 'critical',
            }
        )

    tls_entries = [item for item in (details.get('tls') or []) if isinstance(item, dict)]
    tls_reference_entries = {
        str(item.get('secret_name') or f'TLS Entry {index + 1}'): ', '.join(item.get('hosts') or []) or 'No hosts declared'
        for index, item in enumerate(tls_entries)
    }
    tls_secrets = sorted(
        {str(item.get('secret_name')) for item in tls_entries if item.get('secret_name') not in (None, '', '-')}
    )
    labels = dict(sorted((details.get('labels') or {}).items()))
    annotations = dict(sorted((details.get('annotations') or {}).items()))
    missing_backend_count = sum(1 for item in resolved_paths if item['reference_state'] == 'Missing')

    if not resolved_paths:
        operational_context = {
            'title': 'Review Routing Declaration',
            'description': 'No backend route is represented in the committed snapshot. Confirm the intended Ingress rules and default backend.',
            'icon': 'route-off',
            'tone': 'warning',
        }
    elif missing_backend_count:
        operational_context = {
            'title': 'Resolve Backend References',
            'description': f'{missing_backend_count} backend Service reference could not be resolved in the current committed Service Inventory.',
            'icon': 'unlink',
            'tone': 'critical',
        }
    elif not addresses:
        operational_context = {
            'title': 'Await Controller Publication',
            'description': 'No publication address is reported yet. Confirm the Ingress controller continues reconciling the declared routes.',
            'icon': 'clock-3',
            'tone': 'pending',
        }
    elif not ingress.tls_enabled:
        operational_context = {
            'title': 'TLS Reference Not Configured',
            'description': 'No TLS Secret reference is declared. This remains factual inventory evidence until an explicit governance policy requires TLS.',
            'icon': 'shield-off',
            'tone': 'info',
        }
    else:
        operational_context = {
            'title': 'Ingress Snapshot Ready for Review',
            'description': 'Publication and backend references are represented in the committed snapshot. Live traffic and certificate health remain outside inventory scope.',
            'icon': 'circle-check',
            'tone': 'normal',
        }

    detail_posture_label = (
        'Missing Backends'
        if missing_backend_count
        else ('No Routes' if not resolved_paths else ('Address Pending' if not addresses else 'Published'))
    )
    detail_posture_tone = (
        'critical'
        if missing_backend_count
        else ('warning' if not resolved_paths else ('pending' if not addresses else 'normal'))
    )
    first_host = hosts[0] if hosts else None
    declared_host_url = f'{"https" if ingress.tls_enabled else "http"}://{first_host}' if first_host else None
    return {
        'id': ingress.id,
        'cluster_name': cluster_name,
        'cluster_id': ingress.cluster_id,
        'namespace': ingress.namespace,
        'name': ingress.ingress_name,
        'class': ingress.ingress_class or 'Not Reported',
        'uid': details.get('uid') or '-',
        'generation': int(details.get('generation') or 0),
        'hosts': hosts,
        'addresses': addresses,
        'declared_host_url': declared_host_url,
        'tls': ingress.tls_enabled,
        'tls_entries': tls_entries,
        'tls_reference_entries': tls_reference_entries,
        'tls_secrets': tls_secrets,
        'backend_paths': resolved_paths,
        'backend_resources': backend_resources,
        'backend_count': len(resolved_paths),
        'host_count': len(hosts),
        'service_count': len(service_names),
        'missing_backend_count': missing_backend_count,
        'rule_count': int(details.get('rule_count') or 0),
        'default_backend': details.get('default_backend'),
        'finalizers': details.get('finalizers') or [],
        'finalizer_entries': {str(value): 'Lifecycle finalizer' for value in (details.get('finalizers') or [])},
        'host_entries': {str(value): 'Declared host' for value in hosts},
        'address_entries': {str(value): 'Controller-published address' for value in addresses},
        'age': format_age(ingress.created_at),
        'created_at': ingress.created_at,
        'collected_at': ingress.collected_at,
        'labels': labels,
        'annotations': annotations,
        'detail_posture_label': detail_posture_label,
        'detail_posture_tone': detail_posture_tone,
        'operational_context': operational_context,
    }
