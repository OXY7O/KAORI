from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.extensions import db
from app.inventory.resources.common import filter_current_generation, format_age
from app.models import Cluster, IngressInventory


def get_ingress_filter_classes(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(IngressInventory.ingress_class)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)

    rows = query.distinct().order_by(IngressInventory.ingress_class).all()
    return [row[0] for row in rows if row[0]]


def get_ingress_inventory(
    cluster_id=None,
    namespace=None,
    ingress_class=None,
    tls_status=None,
    search=None,
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

    ingresses = query.order_by(
        Cluster.name,
        IngressInventory.namespace,
        IngressInventory.ingress_name,
    ).all()

    namespace_query = db.session.query(IngressInventory.namespace).distinct()
    if cluster_id:
        namespace_query = namespace_query.filter(IngressInventory.cluster_id == cluster_id)
    namespaces = sorted([ns for (ns,) in namespace_query.all() if ns])

    ingress_data: list[dict[str, Any]] = []
    tls_enabled_count = 0
    hosts: set[str] = set()
    classes: set[str] = set()

    for ingress, cluster_name in ingresses:
        details = ingress.details or {}
        ingress_hosts = [value for value in (details.get('hosts') or []) if value]
        if not ingress_hosts and ingress.host and ingress.host != '-':
            ingress_hosts = [ingress.host]

        tls_entries = details.get('tls') or []
        if ingress.tls_enabled:
            tls_enabled_count += 1
        hosts.update(ingress_hosts)
        if ingress.ingress_class:
            classes.add(ingress.ingress_class)

        ingress_data.append(
            {
                'id': ingress.id,
                'cluster_name': cluster_name,
                'namespace': ingress.namespace,
                'name': ingress.ingress_name,
                'class': ingress.ingress_class or '-',
                'host': ingress_hosts[0] if ingress_hosts else '-',
                'host_count': len(ingress_hosts),
                'address': ingress.address or '-',
                'tls': ingress.tls_enabled,
                'tls_secret_count': len(
                    {
                        item.get('secret_name')
                        for item in tls_entries
                        if isinstance(item, dict) and item.get('secret_name') not in (None, '', '-')
                    }
                ),
                'backend_count': len(ingress.backend_paths or []),
                'created_at': ingress.created_at,
                'collected_at': ingress.collected_at,
            }
        )

    return {
        'total_ingresses': len(ingresses),
        'tls_enabled': tls_enabled_count,
        'tls_disabled': len(ingresses) - tls_enabled_count,
        'total_hosts': len(hosts),
        'ingress_classes': len(classes),
        'classes': get_ingress_filter_classes(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'namespaces': namespaces,
        'ingresses': ingress_data,
        'total_namespaces': len(namespaces),
    }


def get_ingress_detail(
    ingress_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            IngressInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == IngressInventory.cluster_id)
        .filter(IngressInventory.id == ingress_id)
        .first()
    )

    if result is None:
        return None

    ingress, cluster_name = result
    backend_paths = ingress.backend_paths or []
    details = dict(ingress.details or {})
    raw_hosts = [value for value in (details.get('hosts') or []) if value]
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
