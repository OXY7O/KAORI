from __future__ import annotations

from typing import Any


UNKNOWN_FILTER = '__unknown__'


def effective_service_type(service_type: str | None, cluster_ip: str | None) -> str:
    raw_type = str(service_type or '').strip() or 'Unknown'
    return 'Headless' if raw_type == 'ClusterIP' and cluster_ip == 'None' else raw_type


def access_model(service_type: str) -> str:
    return {
        'ClusterIP': 'Cluster Internal',
        'Headless': 'Direct Pod Discovery',
        'NodePort': 'Node Port Publication',
        'LoadBalancer': 'Load Balancer Publication',
        'ExternalName': 'External DNS Alias',
        'Unknown': 'Not Reported',
    }.get(service_type, service_type)


def backend_registration(
    service_type: str,
    selector: dict[str, str],
    endpoints: dict[str, Any],
) -> dict[str, Any]:
    ready = len(endpoints.get('ready_addresses') or [])
    not_ready = len(endpoints.get('not_ready_addresses') or [])
    reported = bool(endpoints.get('reported')) if 'reported' in endpoints else bool(endpoints)
    source = str(endpoints.get('source') or 'Endpoint Evidence')
    total = ready + not_ready

    base = {
        'ready': ready,
        'not_ready': not_ready,
        'reported': reported,
        'source': source,
    }
    if service_type == 'ExternalName':
        return {
            **base,
            'label': 'External Destination',
            'tone': 'info',
            'supporting': 'Endpoint registration not applicable',
            'exception': False,
        }
    if not reported:
        return {
            **base,
            'label': 'Not Reported',
            'tone': 'unknown',
            'supporting': 'Endpoint evidence unavailable',
            'exception': True,
        }
    if not selector:
        tone = 'warning' if not_ready or total == 0 else 'info'
        if ready and not_ready:
            supporting = f'{ready} ready · {not_ready} not ready'
        elif not_ready:
            supporting = f'{not_ready} not ready'
        else:
            supporting = f'{ready} registered address' + ('' if ready == 1 else 'es')
        return {
            **base,
            'label': 'Manually Managed',
            'tone': tone,
            'supporting': supporting,
            'exception': bool(not_ready or total == 0),
        }
    if ready > 0 and not_ready == 0:
        return {
            **base,
            'label': 'Registered',
            'tone': 'normal',
            'supporting': f'{ready} ready',
            'exception': False,
        }
    if ready > 0 and not_ready > 0:
        return {
            **base,
            'label': 'Partial',
            'tone': 'warning',
            'supporting': f'{ready} ready · {not_ready} not ready',
            'exception': True,
        }
    if not_ready > 0:
        return {
            **base,
            'label': 'Not Ready',
            'tone': 'critical',
            'supporting': f'{not_ready} not ready',
            'exception': True,
        }
    return {
        **base,
        'label': 'No Registered Backends',
        'tone': 'warning',
        'supporting': '0 registered addresses',
        'exception': True,
    }


def port_mapping(port_rows: list[dict[str, Any]]) -> tuple[str, str]:
    if not port_rows:
        return 'Not Configured', 'No Service port declared'
    first = port_rows[0]
    service_port = int(first.get('port') or 0)
    target = first.get('target_port') or str(service_port or 'Not Reported')
    protocol = first.get('protocol') or 'TCP'
    primary = f'{service_port}/{protocol} → {target}'
    supporting = f'{len(port_rows)} ' + ('Port' if len(port_rows) == 1 else 'Ports')
    return primary, supporting


def access_presentation(
    service_type: str,
    cluster_ips: list[str],
    external_addresses: list[str],
    external_name: str | None,
) -> tuple[str, str]:
    usable_cluster_ips = [value for value in cluster_ips if value and value != 'None']
    if service_type == 'ExternalName':
        return external_name or 'Not Reported', 'External DNS target'
    if service_type == 'Headless':
        return 'No Cluster IP', 'Direct endpoint discovery'
    if service_type == 'LoadBalancer':
        if external_addresses:
            return external_addresses[0], 'Load balancer address'
        if usable_cluster_ips:
            return usable_cluster_ips[0], 'External address not reported'
        return 'Not Reported', 'Load balancer identity unavailable'
    if service_type == 'NodePort':
        return (usable_cluster_ips[0] if usable_cluster_ips else 'Not Reported'), 'NodePort declarations available'
    return (usable_cluster_ips[0] if usable_cluster_ips else 'Not Reported'), 'Cluster network identity'


def operational_context(registration: dict[str, Any]) -> dict[str, str]:
    contexts = {
        'No Registered Backends': (
            'Review Service Backend Registration',
            'No registered backend address is present for this selector-based Service. '
            'Confirm selector matching and workload readiness.',
            'route-off',
            'warning',
        ),
        'Partial': (
            'Investigate Not-Ready Endpoints',
            'Ready and not-ready backend addresses are both present. Review selected Pod '
            'readiness and endpoint conditions.',
            'triangle-alert',
            'warning',
        ),
        'Not Ready': (
            'Restore Backend Readiness',
            'All reported backend addresses are not ready. Review selected Pods and endpoint '
            'conditions before relying on this Service.',
            'shield-alert',
            'critical',
        ),
        'Not Reported': (
            'Refresh Endpoint Evidence',
            'Endpoint registration evidence was not reported. Run inventory sync before '
            'drawing backend readiness conclusions.',
            'refresh-cw',
            'warning',
        ),
        'External Destination': (
            'Review External Destination',
            'This ExternalName Service delegates resolution to an external DNS destination. '
            'Inventory does not validate destination reachability.',
            'external-link',
            'info',
        ),
    }
    if registration['label'] == 'Manually Managed' and registration['exception']:
        return {
            'title': 'Review Manual Endpoint Registration',
            'description': (
                'This selectorless Service has missing or not-ready manual endpoint registration. '
                'Validate the owning integration and endpoint records.'
            ),
            'icon': 'route-off',
            'tone': 'warning',
        }
    title, description, icon, tone = contexts.get(
        registration['label'],
        (
            'Service Snapshot Ready for Review',
            'Backend registration evidence is available in the committed snapshot. Traffic '
            'health and reachability remain outside inventory scope.',
            'circle-check',
            'normal',
        ),
    )
    return {'title': title, 'description': description, 'icon': icon, 'tone': tone}
