from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class StorageInput:
    cluster: dict[str, Any]
    filesystem: dict[str, Any]
    filesystem_summary: dict[str, Any]
    persistent: dict[str, Any]
    pv: dict[str, Any]
    pvc: dict[str, Any]
    filesystem_rows: list[dict[str, Any]]
    pv_rows: list[dict[str, Any]]
    pvc_rows: list[dict[str, Any]]


def normalize_storage_input(payload: Mapping[str, Any]) -> StorageInput:
    cluster = mapping(payload.get('cluster'))
    storage_summary = mapping(payload.get('storage_summary'))
    filesystem = mapping(storage_summary.get('node_filesystem'))
    persistent = mapping(storage_summary.get('persistent_storage'))
    return StorageInput(
        cluster=cluster,
        filesystem=filesystem,
        filesystem_summary=mapping(filesystem.get('summary')),
        persistent=persistent,
        pv=mapping(persistent.get('pv')),
        pvc=mapping(persistent.get('pvc')),
        filesystem_rows=rows(filesystem.get('all_rows') or filesystem.get('rows')),
        pv_rows=rows(persistent.get('pv_all_rows') or persistent.get('pv_rows')),
        pvc_rows=rows(persistent.get('pvc_all_rows') or persistent.get('pvc_rows')),
    )


def mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return number


def safe_int(value: Any, default: int = 0) -> int:
    number = safe_float(value)
    return int(number) if number is not None else default


def text(value: Any, fallback: str = 'Not Available') -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    return result or fallback


def metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def percent(value: Any, fallback: str = 'Not Available') -> str:
    number = safe_float(value)
    return f'{number:.1f}%' if number is not None else fallback


def status_from_percent(percent_value: float | None) -> tuple[str, str]:
    if percent_value is None:
        return 'Not Available', 'warning'
    if percent_value >= 85:
        return 'Critical', 'critical'
    if percent_value >= 70:
        return 'Warning', 'warning'
    return 'Normal', 'normal'


def risk_tone(value: Any) -> str:
    value_mapping = mapping(value)
    tone = text(value_mapping.get('tone'), '').lower()
    if tone in {'normal', 'warning', 'critical', 'info'}:
        return tone
    label = text(value_mapping.get('label'), '').lower()
    if label in {'critical', 'high'}:
        return 'critical'
    if label in {'warning', 'watch', 'medium'}:
        return 'warning'
    if label in {'healthy', 'normal', 'available'}:
        return 'normal'
    return 'muted'


def risk_label(value: Any) -> str:
    return text(mapping(value).get('label'), 'Not Available')


def format_temporal(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime('%d %b %Y %H:%M UTC')
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    return text(value)


def node_count(payload: Mapping[str, Any], filesystem: Mapping[str, Any]) -> int:
    cluster_info = mapping(payload.get('cluster_info'))
    total = safe_int(cluster_info.get('total_nodes'))
    if total:
        return total
    nodes = filesystem.get('available_nodes')
    if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes, bytearray)):
        return len(set(str(item) for item in nodes if item))
    return len(
        {str(row.get('node')) for row in rows(filesystem.get('all_rows') or filesystem.get('rows')) if row.get('node')}
    )
