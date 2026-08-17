from __future__ import annotations

from typing import (
    Any,
    Literal,
    cast,
    overload,
)

from kubernetes.client import NetworkingV1Api, V1IngressList
from kubernetes.client.exceptions import ApiException

from app.kubernetes.inventory.collectors.common import (
    _mapping_dict,
    _metadata_details,
    _model_value,
    _string_value,
    _to_modelish,
)

COLLECTED = 'Collected'
PERMISSION_UNAVAILABLE = 'Permission Unavailable'
API_UNAVAILABLE = 'API Unavailable'
ADAPTER_NOT_SELECTED = 'Adapter Not Selected'


def _collection_error_state(exc: ApiException) -> str:
    return PERMISSION_UNAVAILABLE if getattr(exc, 'status', None) == 403 else API_UNAVAILABLE


def _backend_port_value(port: Any) -> str | None:
    if port is None:
        return None
    name = _model_value(port, 'name')
    if name not in (None, ''):
        return str(name)
    number = _model_value(port, 'number')
    if number is not None:
        return str(number)
    if isinstance(port, (str, int)):
        return str(port)
    return None


def _backend_to_dict(backend: Any) -> dict[str, Any]:
    service = _model_value(backend, 'service')
    if service is not None:
        return {
            'backend_type': 'Service',
            'service_name': _string_value(_model_value(service, 'name'), ''),
            'service_port': _backend_port_value(_model_value(service, 'port')),
            'resource_api_group': None,
            'resource_kind': None,
            'resource_name': None,
        }

    resource = _model_value(backend, 'resource')
    if resource is not None:
        return {
            'backend_type': 'Resource',
            'service_name': None,
            'service_port': None,
            'resource_api_group': _string_value(_model_value(resource, 'api_group', 'apiGroup'), ''),
            'resource_kind': _string_value(_model_value(resource, 'kind'), ''),
            'resource_name': _string_value(_model_value(resource, 'name'), ''),
        }

    # Kubernetes networking/extensions v1beta1 provider schema. This is
    # normalized here so every downstream KAORI consumer sees one contract.
    legacy_service_name = _model_value(backend, 'service_name', 'serviceName')
    legacy_service_port = _model_value(backend, 'service_port', 'servicePort')
    if legacy_service_name not in (None, '') or legacy_service_port not in (None, ''):
        return {
            'backend_type': 'Service',
            'service_name': _string_value(legacy_service_name, ''),
            'service_port': _backend_port_value(legacy_service_port),
            'resource_api_group': None,
            'resource_kind': None,
            'resource_name': None,
        }

    return {
        'backend_type': 'Unknown',
        'service_name': None,
        'service_port': None,
        'resource_api_group': None,
        'resource_kind': None,
        'resource_name': None,
    }


def _route_entry(
    backend: Any,
    *,
    host: str,
    path: str,
    path_type: str,
    route_source: str,
) -> dict[str, Any]:
    return {
        'host': host,
        'path': path,
        'path_type': path_type,
        'route_source': route_source,
        **_backend_to_dict(backend),
    }


def _ingress_class(metadata: Any, spec: Any) -> tuple[str | None, str]:
    explicit = _model_value(spec, 'ingress_class_name', 'ingressClassName')
    if explicit not in (None, ''):
        return str(explicit), 'spec.ingressClassName'
    annotations = _mapping_dict(_model_value(metadata, 'annotations', default={}))
    legacy = annotations.get('kubernetes.io/ingress.class')
    if legacy not in (None, ''):
        return str(legacy), 'kubernetes.io/ingress.class annotation'
    return None, 'Not Explicitly Set'


def _publication_addresses(status: Any) -> tuple[list[str], bool]:
    load_balancer = _model_value(status, 'load_balancer', 'loadBalancer')
    reported = status is not None and load_balancer is not None
    addresses: list[str] = []
    for item in _model_value(load_balancer, 'ingress', default=[]) or []:
        value = _model_value(item, 'ip') or _model_value(item, 'hostname')
        if value not in (None, '') and str(value) not in addresses:
            addresses.append(str(value))
    return addresses, reported


def _tls_entries(spec: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for tls in _model_value(spec, 'tls', default=[]) or []:
        entries.append(
            {
                'secret_name': _string_value(_model_value(tls, 'secret_name', 'secretName'), ''),
                'hosts': [str(value) for value in (_model_value(tls, 'hosts', default=[]) or []) if value],
            }
        )
    return entries


def _collect_ingress_items(api: NetworkingV1Api | None) -> tuple[list[Any], str]:
    if api is None:
        return [], ADAPTER_NOT_SELECTED
    try:
        result = cast(V1IngressList, api.list_ingress_for_all_namespaces())
    except AttributeError:
        return [], API_UNAVAILABLE
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            return [], _collection_error_state(exc)
        raise
    return list(result.items or []), COLLECTED


def _collect_routes(spec: Any) -> tuple[list[dict[str, Any]], list[str], int, dict[str, Any] | None]:
    routes: list[dict[str, Any]] = []
    hosts: list[str] = []
    hostless_rule_count = 0
    default_backend = None

    backend = _model_value(spec, 'default_backend', 'backend')
    if backend is not None:
        default_backend = _route_entry(
            backend,
            host='All Hosts',
            path='All Paths',
            path_type='Default Backend',
            route_source='Default Backend',
        )
        routes.append(default_backend)

    for rule in _model_value(spec, 'rules', default=[]) or []:
        raw_host = _model_value(rule, 'host')
        host = str(raw_host).strip() if raw_host not in (None, '') else 'All Hosts'
        if host == 'All Hosts':
            hostless_rule_count += 1
        elif host not in hosts:
            hosts.append(host)

        http_rule = _model_value(rule, 'http')
        for path in _model_value(http_rule, 'paths', default=[]) or []:
            path_value = _model_value(path, 'path')
            path_type = _model_value(path, 'path_type', 'pathType')
            routes.append(
                _route_entry(
                    _model_value(path, 'backend'),
                    host=host,
                    path=str(path_value) if path_value not in (None, '') else '/',
                    path_type=str(path_type) if path_type not in (None, '') else 'Not Reported',
                    route_source='Rule',
                )
            )
    return routes, hosts, hostless_rule_count, default_backend


@overload
def get_ingresses(
    api: NetworkingV1Api | None = None,
    *,
    ingress_items: list[Any] | None = None,
    with_evidence: Literal[False] = False,
) -> list[dict[str, Any]]: ...


@overload
def get_ingresses(
    api: NetworkingV1Api | None = None,
    *,
    ingress_items: list[Any] | None = None,
    with_evidence: Literal[True],
) -> tuple[list[dict[str, Any]], dict[str, str]]: ...


def get_ingresses(
    api: NetworkingV1Api | None = None,
    *,
    ingress_items: list[Any] | None = None,
    with_evidence: bool = False,
):
    if ingress_items is None:
        ingress_items, collection_state = _collect_ingress_items(api)
    else:
        collection_state = COLLECTED

    rows: list[dict[str, Any]] = []
    for raw_ingress in ingress_items:
        ingress = _to_modelish(raw_ingress)
        metadata = _model_value(ingress, 'metadata')
        spec = _model_value(ingress, 'spec')
        status = _model_value(ingress, 'status')
        namespace = _model_value(metadata, 'namespace')
        name = _model_value(metadata, 'name')
        if metadata is None or spec is None or not namespace or not name:
            continue

        backend_paths, hosts, hostless_rule_count, default_backend = _collect_routes(spec)
        addresses, publication_reported = _publication_addresses(status)
        tls_entries = _tls_entries(spec)
        ingress_class, ingress_class_source = _ingress_class(metadata, spec)
        metadata_details = _metadata_details(metadata)
        details = {
            **metadata_details,
            'generation': int(_model_value(metadata, 'generation', default=0) or 0),
            'specification_evidence_reported': True,
            'publication_evidence_reported': publication_reported,
            'hosts': hosts,
            'hostless_rule_count': hostless_rule_count,
            'addresses': addresses,
            'tls': tls_entries,
            'rule_count': len(_model_value(spec, 'rules', default=[]) or []),
            'default_backend': default_backend,
            'ingress_class_source': ingress_class_source,
            'finalizers': list(_model_value(metadata, 'finalizers', default=[]) or []),
        }
        rows.append(
            {
                'namespace': str(namespace),
                'ingress_name': str(name),
                'ingress_class': ingress_class,
                'tls_enabled': bool(tls_entries),
                'backend_paths': backend_paths,
                'details': details,
                'created_at': _model_value(metadata, 'creation_timestamp', 'creationTimestamp'),
            }
        )

    evidence = {'inventory.ingresses': collection_state}
    return (rows, evidence) if with_evidence else rows
