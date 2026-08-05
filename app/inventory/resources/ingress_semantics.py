from __future__ import annotations

from typing import Any


UNSET_CLASS_FILTER = '__unset__'
COLLECTED = 'Collected'


def ingress_class_presentation(class_name: str | None, source: str | None = None) -> tuple[str, str]:
    if class_name and str(class_name).strip():
        return str(class_name).strip(), str(source or 'Explicit class declaration')
    return 'Not Explicitly Set', 'Controller default is not inferred'


def host_presentation(details: dict[str, Any]) -> tuple[str, str, int]:
    hosts = [str(value) for value in (details.get('hosts') or []) if value]
    hostless_rules = int(details.get('hostless_rule_count') or 0)
    if hosts:
        supporting = f'{len(hosts)} declared host' + ('' if len(hosts) == 1 else 's')
        if hostless_rules:
            supporting += f' · {hostless_rules} all-host rule' + ('' if hostless_rules == 1 else 's')
        return hosts[0], supporting, len(hosts)
    if hostless_rules:
        return 'All Hosts', f'{hostless_rules} hostless rule' + ('' if hostless_rules == 1 else 's'), 0
    if details.get('specification_evidence_reported') is False:
        return 'Not Reported', 'Ingress specification unavailable', 0
    return 'No Host Rules', 'No rule host declaration', 0


def publication_presentation(details: dict[str, Any]) -> dict[str, Any]:
    addresses = [str(value) for value in (details.get('addresses') or []) if value]
    reported = bool(details.get('publication_evidence_reported'))
    if addresses:
        return {
            'label': 'Published',
            'tone': 'normal',
            'address': addresses[0],
            'addresses': addresses,
            'supporting': f'{len(addresses)} controller address' + ('' if len(addresses) == 1 else 'es'),
            'exception': False,
            'reported': reported,
        }
    if reported:
        return {
            'label': 'Address Pending',
            'tone': 'pending',
            'address': 'No Address Assigned',
            'addresses': [],
            'supporting': 'Controller status reported without an address',
            'exception': True,
            'reported': True,
        }
    return {
        'label': 'Not Reported',
        'tone': 'unknown',
        'address': 'Not Reported',
        'addresses': [],
        'supporting': 'Controller publication evidence unavailable',
        'exception': True,
        'reported': False,
    }


def route_backend_identity(route: dict[str, Any]) -> tuple[str, str]:
    backend_type = str(route.get('backend_type') or 'Unknown')
    if backend_type == 'Service':
        name = str(route.get('service_name') or 'Not Reported')
        port = str(route.get('service_port') or 'Not Reported')
        return name, f'Service · Port {port}'
    if backend_type == 'Resource':
        kind = str(route.get('resource_kind') or 'Resource')
        name = str(route.get('resource_name') or 'Not Reported')
        api_group = str(route.get('resource_api_group') or 'core')
        return f'{kind}/{name}', f'Resource backend · {api_group}'
    return 'Not Reported', 'Backend identity unavailable'


def route_reference_state(
    route: dict[str, Any],
    *,
    service_exists: bool,
    service_collection_state: str,
) -> tuple[str, str]:
    backend_type = str(route.get('backend_type') or 'Unknown')
    if backend_type == 'Resource':
        return 'Resource Backend', 'info'
    if backend_type != 'Service' or not route.get('service_name'):
        return 'Not Reported', 'unknown'
    if service_collection_state != COLLECTED:
        return 'Not Reported', 'unknown'
    if service_exists:
        return 'Resolved', 'normal'
    return 'Missing', 'critical'


def tls_reference_state(secret_exists: bool, secret_collection_state: str) -> tuple[str, str]:
    if secret_collection_state != COLLECTED:
        return 'Not Reported', 'unknown'
    if secret_exists:
        return 'Resolved', 'normal'
    return 'Missing', 'critical'
