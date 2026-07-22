from __future__ import annotations

from typing import (
    Any,
    cast,
)
from kubernetes.client import (
    CoreV1Api,
    V1EndpointsList,
    V1ServiceList,
)
from kubernetes.client.exceptions import ApiException

from app.inventory.collectors.common import _metadata_details, _string_value

def _service_endpoint_map(api: CoreV1Api) -> dict[tuple[str, str], dict]:
    endpoint_map: dict[tuple[str, str], dict] = {}

    try:
        result = cast(
            V1EndpointsList,
            api.list_endpoints_for_all_namespaces(),
        )
    except ApiException:
        return endpoint_map

    for endpoint in result.items or []:
        metadata = endpoint.metadata
        if metadata is None or not metadata.namespace or not metadata.name:
            continue

        ready_addresses: list[dict[str, str]] = []
        not_ready_addresses: list[dict[str, str]] = []
        endpoint_ports: list[dict[str, str | int]] = []

        for subset in endpoint.subsets or []:
            for address in subset.addresses or []:
                target_ref = getattr(address, 'target_ref', None)
                ready_addresses.append(
                    {
                        'ip': _string_value(getattr(address, 'ip', None)),
                        'hostname': _string_value(getattr(address, 'hostname', None)),
                        'node_name': _string_value(getattr(address, 'node_name', None)),
                        'target_kind': _string_value(getattr(target_ref, 'kind', None)),
                        'target_name': _string_value(getattr(target_ref, 'name', None)),
                    }
                )

            for address in subset.not_ready_addresses or []:
                target_ref = getattr(address, 'target_ref', None)
                not_ready_addresses.append(
                    {
                        'ip': _string_value(getattr(address, 'ip', None)),
                        'hostname': _string_value(getattr(address, 'hostname', None)),
                        'node_name': _string_value(getattr(address, 'node_name', None)),
                        'target_kind': _string_value(getattr(target_ref, 'kind', None)),
                        'target_name': _string_value(getattr(target_ref, 'name', None)),
                    }
                )

            for port in subset.ports or []:
                endpoint_ports.append(
                    {
                        'name': _string_value(getattr(port, 'name', None)),
                        'port': int(getattr(port, 'port', 0) or 0),
                        'protocol': _string_value(getattr(port, 'protocol', None), 'TCP'),
                    }
                )

        endpoint_map[(metadata.namespace, metadata.name)] = {
            'reported': True,
            'ready_addresses': ready_addresses,
            'not_ready_addresses': not_ready_addresses,
            'ports': endpoint_ports,
        }

    return endpoint_map


def get_services(
    api: CoreV1Api,
) -> list[dict]:
    result = cast(
        V1ServiceList,
        api.list_service_for_all_namespaces(),
    )
    endpoint_map = _service_endpoint_map(api)
    services: list[dict] = []

    for svc in result.items or []:
        metadata = svc.metadata
        spec = svc.spec
        status = svc.status

        if metadata is None or spec is None:
            continue

        port_details: list[dict[str, Any]] = []
        compact_ports: list[str] = []

        for port in spec.ports or []:
            target_port = getattr(port, 'target_port', None)
            target_port_value = (
                getattr(target_port, 'value', None)
                if target_port is not None
                else None
            )
            if target_port_value is None and target_port is not None:
                target_port_value = str(target_port)

            port_value = int(getattr(port, 'port', 0) or 0)
            protocol = _string_value(getattr(port, 'protocol', None), 'TCP')
            compact_ports.append(f'{port_value}/{protocol}')
            port_details.append(
                {
                    'name': _string_value(getattr(port, 'name', None)),
                    'protocol': protocol,
                    'port': port_value,
                    'target_port': _string_value(target_port_value),
                    'node_port': int(getattr(port, 'node_port', 0) or 0),
                    'app_protocol': _string_value(getattr(port, 'app_protocol', None)),
                }
            )

        external_addresses: list[str] = []
        for value in spec.external_ips or []:
            if value and value not in external_addresses:
                external_addresses.append(value)

        load_balancer = getattr(status, 'load_balancer', None)
        for item in getattr(load_balancer, 'ingress', None) or []:
            value = getattr(item, 'ip', None) or getattr(item, 'hostname', None)
            if value and value not in external_addresses:
                external_addresses.append(value)

        metadata_details = _metadata_details(metadata)
        endpoints = endpoint_map.get(
            (metadata.namespace, metadata.name),
            {
                'reported': False,
                'ready_addresses': [],
                'not_ready_addresses': [],
                'ports': [],
            },
        )

        details = {
            **metadata_details,
            'generation': int(getattr(metadata, 'generation', 0) or 0),
            'cluster_ips': list(getattr(spec, 'cluster_ips', None) or []),
            'ip_families': list(getattr(spec, 'ip_families', None) or []),
            'ip_family_policy': _string_value(getattr(spec, 'ip_family_policy', None)),
            'external_name': _string_value(getattr(spec, 'external_name', None)),
            'session_affinity': _string_value(getattr(spec, 'session_affinity', None), 'None'),
            'internal_traffic_policy': _string_value(getattr(spec, 'internal_traffic_policy', None)),
            'external_traffic_policy': _string_value(getattr(spec, 'external_traffic_policy', None)),
            'publish_not_ready_addresses': bool(getattr(spec, 'publish_not_ready_addresses', False)),
            'health_check_node_port': int(getattr(spec, 'health_check_node_port', 0) or 0),
            'load_balancer_class': _string_value(getattr(spec, 'load_balancer_class', None)),
            'allocate_load_balancer_node_ports': getattr(spec, 'allocate_load_balancer_node_ports', None),
            'ports': port_details,
            'endpoints': endpoints,
        }

        services.append(
            {
                'namespace': metadata.namespace,
                'service_name': metadata.name,
                'service_type': spec.type,
                'cluster_ip': spec.cluster_ip,
                'external_ip': ','.join(external_addresses) if external_addresses else '-',
                'ports': ','.join(compact_ports),
                'selector': dict(spec.selector or {}),
                'details': details,
                'created_at': metadata.creation_timestamp,
            }
        )

    return services
