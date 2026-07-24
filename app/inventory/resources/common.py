from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models import PodInventory, ServiceInventory


def format_age(
    created_at,
) -> str:
    if not created_at:
        return '-'

    normalized_created_at = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - normalized_created_at

    days = delta.days

    if days > 0:
        return f'{days}d'

    hours = delta.seconds // 3600

    return f'{hours}h'


def _pod_summary(
    pod: PodInventory,
) -> dict[str, Any]:
    return {
        'id': pod.id,
        'name': pod.pod_name,
        'status': pod.phase or 'Unknown',
        'ready': pod.ready or '-',
        'node': pod.node_name or '-',
        'container_names': pod.container_names or [],
        'container_count': len(pod.container_names or []),
        'age': format_age(pod.created_at),
    }


def _display_boolean(value: Any) -> str:
    if value is True:
        return 'Yes'
    if value is False:
        return 'No'
    return '-'


def _split_inventory_values(value: str | None) -> list[str]:
    return [item.strip() for item in (value or '').split(',') if item.strip() and item.strip() != '-']


def _selector_matches(
    selector: dict[str, str],
    labels: dict[str, str],
) -> bool:
    return bool(selector) and all(labels.get(key) == value for key, value in selector.items())


def _service_port_rows(service: ServiceInventory) -> list[dict[str, Any]]:
    details = service.details or {}
    ports = details.get('ports') or []
    rows: list[dict[str, Any]] = []

    for port in ports:
        if not isinstance(port, dict):
            continue
        rows.append(
            {
                'name': str(port.get('name') or '-'),
                'protocol': str(port.get('protocol') or 'TCP'),
                'port': int(port.get('port') or 0),
                'target_port': str(port.get('target_port') or '-'),
                'node_port': int(port.get('node_port') or 0),
                'app_protocol': str(port.get('app_protocol') or '-'),
            }
        )

    if rows:
        return rows

    for value in _split_inventory_values(service.ports):
        port_value, _, protocol = value.partition('/')
        rows.append(
            {
                'name': '-',
                'protocol': protocol or 'TCP',
                'port': int(port_value) if port_value.isdigit() else 0,
                'target_port': '-',
                'node_port': 0,
                'app_protocol': '-',
            }
        )

    return rows
