from __future__ import annotations

from typing import (
    Any,
    Literal,
    cast,
    overload,
)

from kubernetes.client import (
    CoreV1Api,
    DiscoveryV1Api,
    V1EndpointSliceList,
    V1EndpointsList,
    V1ServiceList,
)
from kubernetes.client.exceptions import ApiException

from app.inventory.collectors.common import _metadata_details, _string_value

COLLECTED = 'Collected'
PERMISSION_UNAVAILABLE = 'Permission Unavailable'
API_UNAVAILABLE = 'API Unavailable'


def _collection_error_state(exc: ApiException) -> str:
    return PERMISSION_UNAVAILABLE if getattr(exc, 'status', None) == 403 else API_UNAVAILABLE


def _empty_endpoint_evidence(source: str, *, reported: bool) -> dict[str, Any]:
    return {
        'reported': reported,
        'source': source,
        'ready_addresses': [],
        'not_ready_addresses': [],
        'ports': [],
    }


def _append_unique(items: list[dict[str, Any]], item: dict[str, Any], keys: tuple[str, ...]) -> None:
    identity = tuple(item.get(key) for key in keys)
    if any(tuple(existing.get(key) for key in keys) == identity for existing in items):
        return
    items.append(item)


def _endpoint_item(endpoint: Any, address: Any) -> dict[str, Any]:
    conditions = getattr(endpoint, 'conditions', None)
    target_ref = getattr(endpoint, 'target_ref', None)
    ready = getattr(conditions, 'ready', None)
    serving = getattr(conditions, 'serving', None)
    terminating = getattr(conditions, 'terminating', None)
    effective_ready = ready is not False and not (terminating is True and serving is not True)
    return {
        'ip': _string_value(address),
        'hostname': _string_value(getattr(endpoint, 'hostname', None), ''),
        'node_name': _string_value(getattr(endpoint, 'node_name', None), ''),
        'target_kind': _string_value(getattr(target_ref, 'kind', None), ''),
        'target_name': _string_value(getattr(target_ref, 'name', None), ''),
        'ready': effective_ready,
        'serving': serving,
        'terminating': terminating,
    }


def _endpoint_slice_map(
    api: DiscoveryV1Api,
) -> tuple[dict[tuple[str, str], dict[str, Any]], bool, str]:
    endpoint_map: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        result = cast(V1EndpointSliceList, api.list_endpoint_slice_for_all_namespaces())
    except AttributeError:
        return endpoint_map, False, API_UNAVAILABLE
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            return endpoint_map, False, _collection_error_state(exc)
        raise

    for endpoint_slice in result.items or []:
        metadata = endpoint_slice.metadata
        labels = getattr(metadata, 'labels', None) or {}
        namespace = getattr(metadata, 'namespace', None)
        service_name = labels.get('kubernetes.io/service-name')
        if not namespace or not service_name:
            continue

        key = (namespace, service_name)
        evidence = endpoint_map.setdefault(key, _empty_endpoint_evidence('EndpointSlice', reported=True))

        for endpoint in getattr(endpoint_slice, 'endpoints', None) or []:
            for address in getattr(endpoint, 'addresses', None) or []:
                if address in (None, ''):
                    continue
                item = _endpoint_item(endpoint, address)
                destination = evidence['not_ready_addresses'] if item['ready'] is False else evidence['ready_addresses']
                _append_unique(
                    destination,
                    item,
                    ('ip', 'hostname', 'node_name', 'target_kind', 'target_name'),
                )

        for port in getattr(endpoint_slice, 'ports', None) or []:
            item = {
                'name': _string_value(getattr(port, 'name', None), ''),
                'port': int(getattr(port, 'port', 0) or 0),
                'protocol': _string_value(getattr(port, 'protocol', None), 'TCP'),
                'app_protocol': _string_value(getattr(port, 'app_protocol', None), ''),
            }
            _append_unique(evidence['ports'], item, ('name', 'port', 'protocol', 'app_protocol'))

    return endpoint_map, True, COLLECTED


def _endpoints_map(
    api: CoreV1Api,
) -> tuple[dict[tuple[str, str], dict[str, Any]], bool, str]:
    endpoint_map: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        result = cast(V1EndpointsList, api.list_endpoints_for_all_namespaces())
    except ApiException as exc:
        if getattr(exc, 'status', None) in {403, 404}:
            return endpoint_map, False, _collection_error_state(exc)
        raise

    for endpoint in result.items or []:
        metadata = endpoint.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        evidence = _empty_endpoint_evidence('Endpoints', reported=True)
        for subset in endpoint.subsets or []:
            for address in subset.addresses or []:
                target_ref = getattr(address, 'target_ref', None)
                item = {
                    'ip': _string_value(getattr(address, 'ip', None)),
                    'hostname': _string_value(getattr(address, 'hostname', None), ''),
                    'node_name': _string_value(getattr(address, 'node_name', None), ''),
                    'target_kind': _string_value(getattr(target_ref, 'kind', None), ''),
                    'target_name': _string_value(getattr(target_ref, 'name', None), ''),
                    'ready': True,
                    'serving': None,
                    'terminating': None,
                }
                _append_unique(
                    evidence['ready_addresses'],
                    item,
                    ('ip', 'hostname', 'node_name', 'target_kind', 'target_name'),
                )

            for address in subset.not_ready_addresses or []:
                target_ref = getattr(address, 'target_ref', None)
                item = {
                    'ip': _string_value(getattr(address, 'ip', None)),
                    'hostname': _string_value(getattr(address, 'hostname', None), ''),
                    'node_name': _string_value(getattr(address, 'node_name', None), ''),
                    'target_kind': _string_value(getattr(target_ref, 'kind', None), ''),
                    'target_name': _string_value(getattr(target_ref, 'name', None), ''),
                    'ready': False,
                    'serving': None,
                    'terminating': None,
                }
                _append_unique(
                    evidence['not_ready_addresses'],
                    item,
                    ('ip', 'hostname', 'node_name', 'target_kind', 'target_name'),
                )

            for port in subset.ports or []:
                item = {
                    'name': _string_value(getattr(port, 'name', None), ''),
                    'port': int(getattr(port, 'port', 0) or 0),
                    'protocol': _string_value(getattr(port, 'protocol', None), 'TCP'),
                    'app_protocol': _string_value(getattr(port, 'app_protocol', None), ''),
                }
                _append_unique(evidence['ports'], item, ('name', 'port', 'protocol', 'app_protocol'))

        endpoint_map[(metadata.namespace, metadata.name)] = evidence

    return endpoint_map, True, COLLECTED


def _service_endpoint_map(
    core_api: CoreV1Api,
    discovery_api: DiscoveryV1Api | None = None,
) -> tuple[dict[tuple[str, str], dict[str, Any]], str, bool, str]:
    endpoint_slice_state = API_UNAVAILABLE
    if discovery_api is not None:
        endpoint_map, available, endpoint_slice_state = _endpoint_slice_map(discovery_api)
        if available:
            return endpoint_map, 'EndpointSlice', True, COLLECTED

    endpoint_map, available, endpoints_state = _endpoints_map(core_api)
    if available:
        return endpoint_map, 'Endpoints', True, COLLECTED
    final_state = (
        PERMISSION_UNAVAILABLE if PERMISSION_UNAVAILABLE in {endpoint_slice_state, endpoints_state} else API_UNAVAILABLE
    )
    return endpoint_map, 'Endpoints', False, final_state


def _service_ports(spec: Any) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for port in getattr(spec, 'ports', None) or []:
        target_port = getattr(port, 'target_port', None)
        target_port_value = getattr(target_port, 'value', None) if target_port is not None else None
        if target_port_value is None and target_port is not None:
            target_port_value = str(target_port)
        port_value = int(getattr(port, 'port', 0) or 0)
        protocol = _string_value(getattr(port, 'protocol', None), 'TCP')
        details.append(
            {
                'name': _string_value(getattr(port, 'name', None), ''),
                'protocol': protocol,
                'port': port_value,
                'target_port': _string_value(target_port_value, ''),
                'node_port': int(getattr(port, 'node_port', 0) or 0),
                'app_protocol': _string_value(getattr(port, 'app_protocol', None), ''),
            }
        )
    return details


def _external_address_evidence(spec: Any, status: Any) -> tuple[list[str], list[str], list[str], bool]:
    declared = list(dict.fromkeys(value for value in (getattr(spec, 'external_ips', None) or []) if value))
    load_balancer = getattr(status, 'load_balancer', None)
    load_balancer_reported = load_balancer is not None
    ingress_addresses: list[str] = []
    for item in getattr(load_balancer, 'ingress', None) or []:
        value = getattr(item, 'ip', None) or getattr(item, 'hostname', None)
        if value and value not in ingress_addresses:
            ingress_addresses.append(value)
    combined = list(dict.fromkeys([*declared, *ingress_addresses]))
    return declared, ingress_addresses, combined, load_balancer_reported


@overload
def get_services(
    api: CoreV1Api,
    discovery_api: DiscoveryV1Api | None = None,
    *,
    with_evidence: Literal[False] = False,
) -> list[dict]: ...


@overload
def get_services(
    api: CoreV1Api,
    discovery_api: DiscoveryV1Api | None = None,
    *,
    with_evidence: Literal[True],
) -> tuple[list[dict], dict[str, str]]: ...


def get_services(
    api: CoreV1Api,
    discovery_api: DiscoveryV1Api | None = None,
    *,
    with_evidence: bool = False,
) -> list[dict] | tuple[list[dict], dict[str, str]]:
    result = cast(V1ServiceList, api.list_service_for_all_namespaces())
    endpoint_map, endpoint_source, endpoint_source_available, endpoint_state = _service_endpoint_map(
        api,
        discovery_api,
    )
    collection_evidence = {
        'inventory.services': COLLECTED,
        'inventory.services.backend-registration': endpoint_state,
    }
    services: list[dict] = []

    for svc in result.items or []:
        metadata = svc.metadata
        spec = svc.spec
        status = svc.status
        if metadata is None or spec is None or not metadata.namespace or not metadata.name:
            continue

        port_details = _service_ports(spec)
        declared_external_ips, load_balancer_ingress, external_addresses, load_balancer_reported = (
            _external_address_evidence(spec, status)
        )
        metadata_details = _metadata_details(metadata)
        endpoints = endpoint_map.get(
            (metadata.namespace, metadata.name),
            _empty_endpoint_evidence(endpoint_source, reported=endpoint_source_available),
        )
        service_type = _string_value(getattr(spec, 'type', None), 'ClusterIP')
        cluster_ip = getattr(spec, 'cluster_ip', None)

        details = {
            **metadata_details,
            'generation': int(getattr(metadata, 'generation', 0) or 0),
            'specification_evidence_reported': True,
            'cluster_ips': list(getattr(spec, 'cluster_ips', None) or []),
            'ip_families': list(getattr(spec, 'ip_families', None) or []),
            'ip_family_policy': _string_value(getattr(spec, 'ip_family_policy', None), ''),
            'external_name': _string_value(getattr(spec, 'external_name', None), ''),
            'declared_external_ips': declared_external_ips,
            'load_balancer_ingress': load_balancer_ingress,
            'external_addresses': external_addresses,
            'load_balancer_status_reported': load_balancer_reported,
            'session_affinity': _string_value(getattr(spec, 'session_affinity', None), 'None'),
            'internal_traffic_policy': _string_value(getattr(spec, 'internal_traffic_policy', None), ''),
            'external_traffic_policy': _string_value(getattr(spec, 'external_traffic_policy', None), ''),
            'publish_not_ready_addresses': bool(getattr(spec, 'publish_not_ready_addresses', False)),
            'health_check_node_port': int(getattr(spec, 'health_check_node_port', 0) or 0),
            'load_balancer_class': _string_value(getattr(spec, 'load_balancer_class', None), ''),
            'allocate_load_balancer_node_ports': getattr(spec, 'allocate_load_balancer_node_ports', None),
            'ports': port_details,
            'endpoints': endpoints,
        }

        services.append(
            {
                'namespace': metadata.namespace,
                'service_name': metadata.name,
                'service_type': service_type,
                'cluster_ip': cluster_ip,
                'selector': dict(getattr(spec, 'selector', None) or {}),
                'details': details,
                'created_at': metadata.creation_timestamp,
            }
        )

    return (services, collection_evidence) if with_evidence else services
