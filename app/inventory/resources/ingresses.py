from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, func, or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import format_age
from app.inventory.resources.ingress_semantics import (
    COLLECTED,
    UNSET_CLASS_FILTER,
    host_presentation,
    ingress_class_presentation,
    publication_presentation,
    route_backend_identity,
    route_reference_state,
    tls_reference_state,
)
from app.models import (
    Cluster,
    ClusterInventory,
    ConfigurationInventory,
    IngressInventory,
    ServiceInventory,
)


def get_ingress_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(IngressInventory.namespace), IngressInventory)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    return [value for (value,) in query.distinct().order_by(IngressInventory.namespace).all() if value]


def get_ingress_filter_classes(cluster_id: str | None = None, namespace: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(IngressInventory.ingress_class), IngressInventory)
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)
    values = {str(value).strip() if value and str(value).strip() else UNSET_CLASS_FILTER for (value,) in query.distinct().all()}
    return sorted(values, key=lambda value: (value == UNSET_CLASS_FILTER, value.lower()))


def ingress_class_filter_label(value: str) -> str:
    return 'Not Explicitly Set' if value == UNSET_CLASS_FILTER else value


def _apply_filters(query, cluster_id=None, namespace=None, ingress_class=None, tls_status=None, search=None):
    if cluster_id:
        query = query.filter(IngressInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(IngressInventory.namespace == namespace)
    if ingress_class == UNSET_CLASS_FILTER:
        query = query.filter(
            or_(
                IngressInventory.ingress_class.is_(None),
                func.trim(IngressInventory.ingress_class) == '',
            )
        )
    elif ingress_class:
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
                IngressInventory.namespace.ilike(pattern),
                IngressInventory.ingress_class.ilike(pattern),
                cast(IngressInventory.details, String).ilike(pattern),
                cast(IngressInventory.backend_paths, String).ilike(pattern),
            )
        )
    return query


def _route_service_names(paths: list[Any]) -> set[str]:
    return {
        str(item.get('service_name'))
        for item in paths
        if isinstance(item, dict)
        and item.get('backend_type') == 'Service'
        and item.get('service_name') not in (None, '')
    }


def _summary_rows(cluster_id=None, namespace=None, ingress_class=None, tls_status=None, search=None):
    query = db.session.query(
        IngressInventory.ingress_class,
        IngressInventory.tls_enabled,
        IngressInventory.backend_paths,
        IngressInventory.details,
    )
    query = filter_current_generation(query, IngressInventory)
    return _apply_filters(query, cluster_id, namespace, ingress_class, tls_status, search).all()


def _summary_metrics(summary_rows) -> dict[str, int]:
    hosts: set[str] = set()
    classes: set[str] = set()
    backend_services: set[str] = set()
    metrics = {
        'backend_route_count': 0,
        'resource_backend_count': 0,
        'tls_ingresses': 0,
        'tls_secret_references': 0,
        'publication_exceptions': 0,
        'routing_exceptions': 0,
        'publication_not_reported': 0,
    }
    for class_name, tls_enabled, backend_paths, details in summary_rows:
        details = details or {}
        hosts.update(str(value) for value in (details.get('hosts') or []) if value)
        class_label, _ = ingress_class_presentation(class_name, details.get('ingress_class_source'))
        classes.add(class_label)
        paths = [item for item in (backend_paths or []) if isinstance(item, dict)]
        backend_services.update(_route_service_names(paths))
        metrics['backend_route_count'] += len(paths)
        metrics['resource_backend_count'] += sum(1 for item in paths if item.get('backend_type') == 'Resource')
        metrics['tls_ingresses'] += int(bool(tls_enabled))
        metrics['tls_secret_references'] += len(
            {
                str(item.get('secret_name'))
                for item in (details.get('tls') or [])
                if isinstance(item, dict) and item.get('secret_name')
            }
        )
        publication = publication_presentation(details)
        metrics['publication_exceptions'] += int(publication['exception'])
        metrics['publication_not_reported'] += int(not publication['reported'])
        if details.get('specification_evidence_reported') is False or not paths:
            metrics['routing_exceptions'] += 1
    return {
        **metrics,
        'total_hosts': len(hosts),
        'ingress_classes': len(classes),
        'backend_service_count': len(backend_services),
    }


def _present_ingress_row(ingress: IngressInventory, cluster_name: str, environment: str) -> dict[str, Any]:
    details = ingress.details or {}
    class_label, class_supporting = ingress_class_presentation(
        ingress.ingress_class,
        details.get('ingress_class_source'),
    )
    host_label, host_supporting, host_count = host_presentation(details)
    publication = publication_presentation(details)
    paths = [item for item in (ingress.backend_paths or []) if isinstance(item, dict)]
    service_names = _route_service_names(paths)
    resource_count = sum(1 for item in paths if item.get('backend_type') == 'Resource')
    tls_entries = [item for item in (details.get('tls') or []) if isinstance(item, dict)]
    tls_secret_count = len({str(item.get('secret_name')) for item in tls_entries if item.get('secret_name')})
    tls_host_count = len({str(host) for item in tls_entries for host in (item.get('hosts') or []) if host})
    route_supporting_parts = [f'{len(service_names)} Services']
    if resource_count:
        route_supporting_parts.append(f'{resource_count} Resource Backends')
    return {
        'id': ingress.id,
        'cluster_name': cluster_name,
        'cluster_environment': environment,
        'namespace': ingress.namespace,
        'name': ingress.ingress_name,
        'class': class_label,
        'class_supporting': class_supporting,
        'host': host_label,
        'host_supporting': host_supporting,
        'host_count': host_count,
        'address': publication['address'],
        'address_count': len(publication['addresses']),
        'publication_label': publication['label'],
        'publication_tone': publication['tone'],
        'publication_supporting': publication['supporting'],
        'tls_reference_label': (
            f'{tls_secret_count} Secret Reference' + ('' if tls_secret_count == 1 else 's')
            if tls_secret_count
            else ('TLS Declared · No Secret Reference' if tls_entries else 'No TLS Reference')
        ),
        'tls_host_count': tls_host_count,
        'backend_count': len(paths),
        'service_count': len(service_names),
        'resource_backend_count': resource_count,
        'routing_label': f'{len(paths)} Route' + ('' if len(paths) == 1 else 's'),
        'routing_supporting': ' · '.join(route_supporting_parts),
        'created_at': ingress.created_at,
        'collected_at': ingress.collected_at,
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
    rows, pagination = paginate_query(
        query.order_by(Cluster.name, IngressInventory.namespace, IngressInventory.ingress_name),
        page=page,
        per_page=per_page,
    )
    summary = _summary_metrics(_summary_rows(cluster_id, namespace, ingress_class, tls_status, search))
    presented = [_present_ingress_row(item, cluster_name, environment) for item, cluster_name, environment in rows]
    total = pagination['total_items']
    exceptions = summary['publication_exceptions'] + summary['routing_exceptions']
    return {
        'total_ingresses': total,
        **summary,
        'overall_posture_label': 'No Data' if total == 0 else ('Attention' if exceptions else 'Represented'),
        'overall_posture_tone': 'unknown' if total == 0 else ('warning' if exceptions else 'normal'),
        'ingresses': presented,
        'pagination': pagination,
    }


def _collection_states(cluster_id: str) -> tuple[str, str]:
    cluster_inventory = ClusterInventory.query.filter_by(cluster_id=cluster_id).first()
    evidence = dict(cluster_inventory.collection_evidence or {}) if cluster_inventory else {}
    return (
        str(evidence.get('inventory.services') or 'Not Reported'),
        str(evidence.get('inventory.secrets') or 'Not Reported'),
    )


def _service_map(ingress: IngressInventory, service_names: set[str]) -> dict[str, ServiceInventory]:
    if not service_names:
        return {}
    query = filter_current_generation(ServiceInventory.query, ServiceInventory).filter(
        ServiceInventory.cluster_id == ingress.cluster_id,
        ServiceInventory.namespace == ingress.namespace,
        ServiceInventory.service_name.in_(sorted(service_names)),
    )
    return {item.service_name: item for item in query.all()}


def _secret_map(ingress: IngressInventory, secret_names: set[str]) -> dict[str, ConfigurationInventory]:
    if not secret_names:
        return {}
    query = filter_current_generation(ConfigurationInventory.query, ConfigurationInventory).filter(
        ConfigurationInventory.cluster_id == ingress.cluster_id,
        ConfigurationInventory.namespace == ingress.namespace,
        ConfigurationInventory.object_type == 'Secret',
        ConfigurationInventory.name.in_(sorted(secret_names)),
    )
    return {item.name: item for item in query.all()}


def _resolved_routes(
    backend_paths: list[dict[str, Any]],
    service_map: dict[str, ServiceInventory],
    service_collection_state: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in backend_paths:
        service_name = str(route.get('service_name') or '')
        service = service_map.get(service_name)
        state, tone = route_reference_state(
            route,
            service_exists=service is not None,
            service_collection_state=service_collection_state,
        )
        backend_name, backend_supporting = route_backend_identity(route)
        rows.append(
            {
                'host': str(route.get('host') or 'Not Reported'),
                'path': str(route.get('path') or 'Not Reported'),
                'path_type': str(route.get('path_type') or 'Not Reported'),
                'route_source': str(route.get('route_source') or 'Not Reported'),
                'backend_type': str(route.get('backend_type') or 'Unknown'),
                'backend_name': backend_name,
                'backend_supporting': backend_supporting,
                'service_name': service_name or None,
                'service_port': route.get('service_port'),
                'reference_state': state,
                'reference_tone': tone,
            }
        )
    return rows


def _related_services(
    ingress: IngressInventory,
    service_names: set[str],
    service_map: dict[str, ServiceInventory],
    service_collection_state: str,
) -> list[dict[str, Any]]:
    rows = []
    for name in sorted(service_names):
        service = service_map.get(name)
        state, tone = route_reference_state(
            {'backend_type': 'Service', 'service_name': name},
            service_exists=service is not None,
            service_collection_state=service_collection_state,
        )
        rows.append(
            {
                'name': name,
                'supporting_primary': f'Namespace {ingress.namespace}',
                'supporting_secondary': (
                    f'{service.service_type or "Not Reported"} · '
                    f'{len((service.details or {}).get("ports") or [])} declared ports'
                    if service
                    else (
                        'Service collection evidence unavailable'
                        if service_collection_state != COLLECTED
                        else 'No matching Service in the committed snapshot'
                    )
                ),
                'status': state,
                'status_tone': tone,
            }
        )
    return rows


def _tls_resources(
    ingress: IngressInventory,
    tls_entries: list[dict[str, Any]],
    secret_collection_state: str,
) -> tuple[list[dict[str, Any]], int, int]:
    secret_names = {str(item.get('secret_name')) for item in tls_entries if item.get('secret_name')}
    secret_map = _secret_map(ingress, secret_names)
    resources = []
    missing = not_reported = 0
    for name in sorted(secret_names):
        secret = secret_map.get(name)
        state, tone = tls_reference_state(secret is not None, secret_collection_state)
        missing += int(state == 'Missing')
        not_reported += int(state == 'Not Reported')
        hosts = sorted({str(host) for item in tls_entries if item.get('secret_name') == name for host in (item.get('hosts') or []) if host})
        resources.append(
            {
                'name': name,
                'supporting_primary': ', '.join(hosts) if hosts else 'No TLS hosts declared',
                'supporting_secondary': (
                    secret.secret_type or 'Secret present in committed inventory'
                    if secret
                    else (
                        'Secret collection evidence unavailable'
                        if secret_collection_state != COLLECTED
                        else 'No matching Secret in the committed inventory'
                    )
                ),
                'status': state,
                'status_tone': tone,
            }
        )
    return resources, missing, not_reported


def _operational_context(
    *,
    specification_reported: bool,
    routes: list[dict[str, Any]],
    publication: dict[str, Any],
    missing_backends: int,
    unresolved_backends: int,
    missing_tls_secrets: int,
    tls_not_reported: int,
    tls_enabled: bool,
) -> dict[str, str]:
    if not specification_reported:
        return {
            'title': 'Refresh Ingress Specification Evidence',
            'description': 'Ingress specification evidence is not represented. Run inventory sync before evaluating routes or TLS references.',
            'icon': 'refresh-cw',
            'tone': 'warning',
        }
    if not routes:
        return {
            'title': 'Review Routing Declaration',
            'description': 'No backend route is represented in the committed snapshot. Confirm rule paths or the default backend.',
            'icon': 'route-off',
            'tone': 'warning',
        }
    if missing_backends:
        return {
            'title': 'Resolve Backend Service References',
            'description': f'{missing_backends} backend Service reference could not be resolved in the current committed Service Inventory.',
            'icon': 'unlink',
            'tone': 'critical',
        }
    if unresolved_backends:
        return {
            'title': 'Refresh Service Inventory Evidence',
            'description': 'Backend Service references cannot be evaluated because Service collection evidence is unavailable.',
            'icon': 'refresh-cw',
            'tone': 'warning',
        }
    if missing_tls_secrets:
        return {
            'title': 'Resolve TLS Secret References',
            'description': f'{missing_tls_secrets} TLS Secret reference could not be resolved in the committed Secret Inventory.',
            'icon': 'key-round',
            'tone': 'critical',
        }
    if tls_not_reported:
        return {
            'title': 'Refresh Secret Inventory Evidence',
            'description': 'TLS Secret references cannot be evaluated because Secret collection evidence is unavailable.',
            'icon': 'refresh-cw',
            'tone': 'warning',
        }
    if publication['label'] == 'Not Reported':
        return {
            'title': 'Refresh Publication Evidence',
            'description': 'Ingress controller publication status was not reported. Confirm controller RBAC and reconcile state before drawing publication conclusions.',
            'icon': 'refresh-cw',
            'tone': 'warning',
        }
    if publication['label'] == 'Address Pending':
        return {
            'title': 'Await Controller Publication',
            'description': 'The controller reported publication status without assigning an address. Confirm that reconciliation is progressing.',
            'icon': 'clock-3',
            'tone': 'pending',
        }
    if not tls_enabled:
        return {
            'title': 'TLS Reference Not Configured',
            'description': 'No TLS Secret reference is declared. This remains neutral inventory evidence until an explicit governance policy evaluates it.',
            'icon': 'shield-off',
            'tone': 'info',
        }
    return {
        'title': 'Ingress Snapshot Ready for Review',
        'description': 'Publication, route references, and Secret references are represented. Live reachability, traffic health, and certificate validity remain outside inventory scope.',
        'icon': 'circle-check',
        'tone': 'normal',
    }


def _detail_reference_context(ingress: IngressInventory, details: dict[str, Any]) -> dict[str, Any]:
    specification_reported = details.get('specification_evidence_reported') is True
    backend_paths = [item for item in (ingress.backend_paths or []) if isinstance(item, dict)]
    service_names = _route_service_names(backend_paths)
    service_collection_state, secret_collection_state = _collection_states(ingress.cluster_id)
    service_map = _service_map(ingress, service_names)
    resolved_paths = _resolved_routes(backend_paths, service_map, service_collection_state)
    backend_resources = _related_services(ingress, service_names, service_map, service_collection_state)
    tls_entries = [item for item in (details.get('tls') or []) if isinstance(item, dict)]
    tls_resources, missing_tls_secrets, tls_not_reported = _tls_resources(
        ingress,
        tls_entries,
        secret_collection_state,
    )
    publication = publication_presentation(details)
    missing_backends = sum(1 for item in resolved_paths if item['reference_state'] == 'Missing')
    unresolved_backends = sum(1 for item in resolved_paths if item['reference_state'] == 'Not Reported')
    resource_backend_count = sum(1 for item in resolved_paths if item['backend_type'] == 'Resource')
    operational_context = _operational_context(
        specification_reported=specification_reported,
        routes=resolved_paths,
        publication=publication,
        missing_backends=missing_backends,
        unresolved_backends=unresolved_backends,
        missing_tls_secrets=missing_tls_secrets,
        tls_not_reported=tls_not_reported,
        tls_enabled=ingress.tls_enabled,
    )
    critical = missing_backends + missing_tls_secrets
    warnings = int(not resolved_paths or publication['exception'] or unresolved_backends > 0 or tls_not_reported > 0)
    return {
        'specification_reported': specification_reported,
        'service_names': service_names,
        'service_collection_state': service_collection_state,
        'secret_collection_state': secret_collection_state,
        'resolved_paths': resolved_paths,
        'backend_resources': backend_resources,
        'tls_entries': tls_entries,
        'tls_resources': tls_resources,
        'missing_tls_secrets': missing_tls_secrets,
        'tls_not_reported': tls_not_reported,
        'publication': publication,
        'missing_backends': missing_backends,
        'unresolved_backends': unresolved_backends,
        'resource_backend_count': resource_backend_count,
        'operational_context': operational_context,
        'detail_label': 'Attention' if critical or warnings else 'Represented',
        'detail_tone': 'critical' if critical else ('warning' if warnings else 'normal'),
    }


def _present_ingress_detail(
    ingress: IngressInventory,
    cluster_name: str,
    details: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    class_label, class_supporting = ingress_class_presentation(
        ingress.ingress_class,
        details.get('ingress_class_source'),
    )
    host_label, host_supporting, host_count = host_presentation(details)
    hosts = [str(value) for value in (details.get('hosts') or []) if value]
    publication = context['publication']
    return {
        'id': ingress.id,
        'cluster_name': cluster_name,
        'cluster_id': ingress.cluster_id,
        'namespace': ingress.namespace,
        'name': ingress.ingress_name,
        'class': class_label,
        'class_supporting': class_supporting,
        'uid': details.get('uid') or 'Not Reported',
        'generation': int(details.get('generation') or 0),
        'specification_reported': context['specification_reported'],
        'host_label': host_label,
        'host_supporting': host_supporting,
        'hosts': hosts,
        'host_count': host_count,
        'hostless_rule_count': int(details.get('hostless_rule_count') or 0),
        'addresses': publication['addresses'],
        'publication_label': publication['label'],
        'publication_tone': publication['tone'],
        'publication_supporting': publication['supporting'],
        'tls': ingress.tls_enabled,
        'tls_entries': context['tls_entries'],
        'tls_resources': context['tls_resources'],
        'tls_secret_count': len(context['tls_resources']),
        'missing_tls_secret_count': context['missing_tls_secrets'],
        'tls_not_reported_count': context['tls_not_reported'],
        'secret_collection_state': context['secret_collection_state'],
        'backend_paths': context['resolved_paths'],
        'backend_resources': context['backend_resources'],
        'backend_count': len(context['resolved_paths']),
        'service_count': len(context['service_names']),
        'resource_backend_count': context['resource_backend_count'],
        'missing_backend_count': context['missing_backends'],
        'unresolved_backend_count': context['unresolved_backends'],
        'service_collection_state': context['service_collection_state'],
        'rule_count': int(details.get('rule_count') or 0),
        'default_backend': details.get('default_backend'),
        'finalizers': details.get('finalizers') or [],
        'finalizer_entries': {str(value): 'Lifecycle finalizer' for value in (details.get('finalizers') or [])},
        'host_entries': {str(value): 'Explicit host declaration' for value in hosts},
        'address_entries': {str(value): 'Controller-published address' for value in publication['addresses']},
        'age': format_age(ingress.created_at),
        'created_at': ingress.created_at,
        'collected_at': ingress.collected_at,
        'labels': dict(sorted((details.get('labels') or {}).items())),
        'annotations': dict(sorted((details.get('annotations') or {}).items())),
        'detail_posture_label': context['detail_label'],
        'detail_posture_tone': context['detail_tone'],
        'operational_context': context['operational_context'],
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
    return _present_ingress_detail(
        ingress,
        cluster_name,
        details,
        _detail_reference_context(ingress, details),
    )
