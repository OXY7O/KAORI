from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from app.dashboards.kubernetes.schema import CapacityItem, CapacitySnapshot, DashboardClusterOption


def get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def normalize_selected_cluster(selected_cluster_id: str | None, clusters: list[DashboardClusterOption]) -> str | None:
    if not selected_cluster_id:
        return None
    valid_ids = {cluster.id for cluster in clusters}
    return selected_cluster_id if selected_cluster_id in valid_ids else None


def get_live_cluster(*, clusters_raw: list[Any], selected_cluster_id: str | None) -> Any | None:
    if not selected_cluster_id:
        return None

    for cluster in clusters_raw:
        if str(get_attr(cluster, 'id', default='')) == selected_cluster_id:
            return cluster

    return None


def normalize_status(value: Any) -> str:
    return str(value or '').strip().lower()


def is_ready_node(node: Any) -> bool:
    status = normalize_status(get_attr(node, 'status', 'condition', 'ready', default=''))
    return status in {'ready', 'true', 'active', 'healthy'}


def is_unhealthy_pod(pod: Any) -> bool:
    status = normalize_status(get_attr(pod, 'status', 'phase', default=''))
    return status in {'pending', 'failed', 'unknown', 'crashloopbackoff', 'imagepullbackoff', 'error'}


def recommendation_icon(card: dict[str, Any]) -> str:
    return {
        'node': 'server-crash',
        'pod': 'container',
        'workload': 'boxes',
        'namespace': 'layout-grid',
        'persistent_volume': 'hard-drive',
        'tls_secret': 'shield-check',
        'cluster': 'gauge',
    }.get(str(card.get('source_kind') or ''), 'sparkles')


def recommendation_href(card: dict[str, Any]) -> str:
    rule_key = str(card.get('rule_key') or '').strip()
    if not rule_key:
        return '/intelligence/recommendations'
    return f'/intelligence/recommendations?q={quote(rule_key, safe="")}'


def plural_suffix(value: int) -> str:
    return '' if value == 1 else 's'


def count_cluster_status(clusters_raw: list[Any], expected: str) -> int:
    count = 0
    for cluster in clusters_raw:
        status = normalize_status(get_attr(cluster, 'status', 'connection_status', 'health', default=''))
        if expected == 'healthy' and status in {'active', 'connected', 'healthy', 'online', ''}:
            count += 1
        elif expected == 'warning' and status in {'warning', 'degraded'}:
            count += 1
    return count


def capacity_percent(snapshot: CapacitySnapshot, label: str) -> float | None:
    for item in snapshot.items:
        if item.label.lower() == label.lower():
            return item.used_percent
    return None


def percent_label(value: float | None) -> str:
    if value is None:
        return '—'
    return f'{value:.0f}%'


def headroom(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, round(100.0 - value, 2))


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def risk_from_percent(value: float) -> str:
    if value >= 90:
        return 'Critical'
    if value >= 75:
        return 'High'
    if value >= 60:
        return 'Medium'
    return 'Low'


def capacity_insight(risk: str, items: list[CapacityItem]) -> str:
    highest = max(items, key=lambda item: safe_float(item.used_percent), default=None)
    if highest is None or highest.used_percent is None:
        return 'Capacity metrics are not available yet.'
    return f'{highest.label} is the highest utilization signal at {highest.used_percent:.0f}%. Overall risk: {risk}.'


def forecast_insight(payload: dict[str, Any]) -> str:
    summary = payload.get('summary')
    if not isinstance(summary, dict):
        return 'Forecast snapshot loaded from analytics forecast service.'
    label = summary.get('highest_projected_label', 'resource')
    percent = summary.get('highest_projected_percent', 0)
    horizon_days = safe_optional_int(payload.get('horizon_days')) or 90
    try:
        return f'{label} has the highest {horizon_days}-day projection at {float(percent):.0f}%.'
    except (TypeError, ValueError):
        return 'Forecast snapshot loaded from analytics forecast service.'



def format_gib(value: Any) -> str:
    number = safe_float(value)
    gib = number / 1024**3
    if gib >= 1024:
        return f'{gib / 1024:.2f} TiB'
    return f'{gib:.2f} GiB'


def latest_timestamp(items: Iterable[Any]) -> datetime | None:
    latest: datetime | None = None
    for item in items:
        value = coerce_datetime(get_attr(item, 'updated_at', 'collected_at', 'created_at', 'last_seen', 'last_sync'))
        if value is None:
            continue
        if latest is None or value > latest:
            latest = value
    return latest


def coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            return None
    return None


def human_time(value: datetime | None) -> str:
    if value is None:
        return 'Unknown'
    now = datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    delta = now - value
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return 'just now'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m ago'
    hours = minutes // 60
    if hours < 24:
        return f'{hours}h ago'
    days = hours // 24
    return f'{days}d ago'
