from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import format_age
from app.models import Cluster, IngressInventory


def get_ingress_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(IngressInventory.namespace)
    query = filter_current_generation(query, IngressInventory)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)

    rows = query.distinct().order_by(IngressInventory.namespace).all()
    return [row[0] for row in rows if row[0]]


def get_ingress_filter_classes(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(IngressInventory.ingress_class)
    query = filter_current_generation(query, IngressInventory)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)

    rows = query.distinct().order_by(IngressInventory.ingress_class).all()
    return [row[0] for row in rows if row[0]]


def _ingress_hosts(host: str | None, details: dict[str, Any]) -> list[str]:
    hosts = [value for value in (details.get('hosts') or []) if value]
    if not hosts and host and host != '-':
        hosts.append(host)
    return hosts


def _ingress_tls_secret_count(tls_entries: list[Any]) -> int:
    return len(
        {
            item.get('secret_name')
            for item in tls_entries
            if isinstance(item, dict) and item.get('secret_name') not in (None, '', '-')
        }
    )


def _ingress_inventory_row(ingress: IngressInventory, cluster_name: str) -> dict[str, Any]:
    details = ingress.details or {}
    ingress_hosts = _ingress_hosts(ingress.host, details)

    return {
        'id': ingress.id,
        'cluster_name': cluster_name,
        'namespace': ingress.namespace,
        'name': ingress.ingress_name,
        'class': ingress.ingress_class or '-',
        'host': ingress_hosts[0] if ingress_hosts else '-',
        'host_count': len(ingress_hosts),
        'address': ingress.address or '-',
        'tls': ingress.tls_enabled,
        'tls_secret_count': _ingress_tls_secret_count(details.get('tls') or []),
        'backend_count': len(ingress.backend_paths or []),
        'created_at': ingress.created_at,
        'collected_at': ingress.collected_at,
    }


def _ingress_summary(summary_rows: list[Any]) -> tuple[int, set[str], set[str], set[str]]:
    tls_enabled_count = 0
    hosts: set[str] = set()
    classes: set[str] = set()
    namespaces: set[str] = set()

    for tls_enabled, host, ingress_class_name, namespace, details in summary_rows:
        tls_enabled_count += int(bool(tls_enabled))
        hosts.update(_ingress_hosts(host, details or {}))
        if ingress_class_name:
            classes.add(ingress_class_name)
        if namespace:
            namespaces.add(namespace)

    return tls_enabled_count, hosts, classes, namespaces


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
    ).join(Cluster, Cluster.id == IngressInventory.cluster_id)
    query = filter_current_generation(query, IngressInventory)

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

    summary_rows = query.with_entities(
        IngressInventory.tls_enabled,
        IngressInventory.host,
        IngressInventory.ingress_class,
        IngressInventory.namespace,
        IngressInventory.details,
    ).all()
    ingresses, pagination = paginate_query(
        query.order_by(
            Cluster.name,
            IngressInventory.namespace,
            IngressInventory.ingress_name,
        ),
        page=page,
        per_page=per_page,
    )

    tls_enabled_count, hosts, classes, namespaces = _ingress_summary(summary_rows)
    ingress_data = [_ingress_inventory_row(ingress, cluster_name) for ingress, cluster_name in ingresses]

    return {
        'total_ingresses': pagination['total_items'],
        'tls_enabled': tls_enabled_count,
        'tls_disabled': pagination['total_items'] - tls_enabled_count,
        'total_hosts': len(hosts),
        'ingress_classes': len(classes),
        'total_namespaces': len(namespaces),
        'ingresses': ingress_data,
        'pagination': pagination,
    }


def get_ingress_detail(
    ingress_id: int,
) -> dict[str, Any] | None:
    query = db.session.query(
        IngressInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == IngressInventory.cluster_id)
    query = filter_current_generation(query, IngressInventory)
    result = query.filter(IngressInventory.id == ingress_id).first()

    if result is None:
        return None

    ingress, cluster_name = result
    backend_paths = ingress.backend_paths or []
    details = dict(ingress.details or {})
    raw_hosts = _ingress_hosts(ingress.host, details)
    if not raw_hosts:
        raw_hosts = sorted(
            {
                str(item.get('host'))
                for item in backend_paths
                if isinstance(item, dict) and item.get('host') not in (None, '', '-')
            }
        )
    services = sorted(
        {
            str(item.get('service_name'))
            for item in backend_paths
            if isinstance(item, dict) and item.get('service_name') not in (None, '', '-')
        }
    )
    tls_entries = [item for item in (details.get('tls') or []) if isinstance(item, dict)]
    tls_secrets = sorted(
        {str(item.get('secret_name')) for item in tls_entries if item.get('secret_name') not in (None, '', '-')}
    )
    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}

    return {
        'id': ingress.id,
        'cluster_name': cluster_name,
        'namespace': ingress.namespace,
        'name': ingress.ingress_name,
        'class': ingress.ingress_class or '-',
        'uid': details.get('uid') or '-',
        'generation': int(details.get('generation') or 0),
        'host': ingress.host or '-',
        'hosts': [
            {
                'value': host,
                'url': f'{"https" if ingress.tls_enabled else "http"}://{host}',
            }
            for host in raw_hosts
        ],
        'address': ingress.address or '-',
        'tls': ingress.tls_enabled,
        'tls_entries': tls_entries,
        'tls_secrets': tls_secrets,
        'backend_paths': backend_paths,
        'backend_count': len(backend_paths),
        'host_count': len(raw_hosts),
        'service_count': len(services),
        'rule_count': int(details.get('rule_count') or 0),
        'default_backend': details.get('default_backend'),
        'finalizers': details.get('finalizers') or [],
        'age': format_age(ingress.created_at),
        'created_at': ingress.created_at,
        'collected_at': ingress.collected_at,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
    }
