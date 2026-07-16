from __future__ import annotations

from typing import Any

from app.dashboards.kubernetes.repository import query_all
from app.dashboards.kubernetes.schema import ClusterHealthPagination, ClusterHealthRow
from app.dashboards.kubernetes.utils import (
    coerce_datetime,
    get_attr,
    human_time,
    is_ready_node,
    is_unhealthy_pod,
    latest_timestamp,
    normalize_status,
    plural_suffix,
    safe_float,
    safe_optional_float,
    safe_optional_int,
)


def _normalize_page_number(value: str | int | None) -> int:
    try:
        page = int(value or 1)
    except (TypeError, ValueError):
        return 1

    return max(page, 1)


def paginate_sequence(
    *,
    items: list[Any],
    page: str | int | None,
    per_page: int = 5,
) -> tuple[list[Any], ClusterHealthPagination]:
    per_page = max(per_page, 1)
    total_items = len(items)
    total_pages = max((total_items + per_page - 1) // per_page, 1)
    current_page = min(_normalize_page_number(page), total_pages)

    start_index = (current_page - 1) * per_page
    end_index = start_index + per_page
    visible_items = items[start_index:end_index]

    if total_items == 0:
        start_item = 0
        end_item = 0
    else:
        start_item = start_index + 1
        end_item = min(end_index, total_items)

    pagination = ClusterHealthPagination(
        page=current_page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
        has_prev=current_page > 1,
        has_next=current_page < total_pages,
        prev_page=max(current_page - 1, 1),
        next_page=min(current_page + 1, total_pages),
        start_item=start_item,
        end_item=end_item,
    )

    return visible_items, pagination


def build_cluster_health(
    *,
    clusters_raw: list[Any],
    selected_cluster_id: str | None,
    NodeInventory: Any,
    PodInventory: Any,
    hydrate_live_signals: bool = True,
) -> list[ClusterHealthRow]:
    rows: list[ClusterHealthRow] = []
    clusters = clusters_raw

    if selected_cluster_id:
        clusters = [
            cluster for cluster in clusters_raw if str(get_attr(cluster, 'id', default='')) == selected_cluster_id
        ]

    for cluster in clusters:
        cluster_id = str(get_attr(cluster, 'id', default=''))
        nodes = query_all(NodeInventory, cluster_id) if NodeInventory else []
        pods = query_all(PodInventory, cluster_id) if PodInventory else []

        inventory_nodes_total = len(nodes)
        inventory_nodes_ready = sum(1 for node in nodes if is_ready_node(node))
        unhealthy_pods = sum(1 for pod in pods if is_unhealthy_pod(pod))

        live_signals = _get_cluster_live_signal_snapshot(cluster) if hydrate_live_signals else None
        cpu_percent = live_signals.get('cpu') if live_signals else None
        memory_percent = live_signals.get('memory') if live_signals else None
        live_nodes_total = safe_optional_int(live_signals.get('nodes_total')) if live_signals else None
        live_nodes_ready = safe_optional_int(live_signals.get('nodes_ready')) if live_signals else None
        nodes_total = live_nodes_total if live_nodes_total is not None else inventory_nodes_total
        nodes_ready = live_nodes_ready if live_nodes_ready is not None else inventory_nodes_ready
        not_ready = max(nodes_total - nodes_ready, 0)
        nodes_status = 'Live' if live_nodes_total is not None and live_nodes_ready is not None else 'Inventory'
        cpu_status = 'Live' if cpu_percent is not None else 'Unavailable'
        memory_status = 'Live' if memory_percent is not None else 'Unavailable'

        alert_summary = _get_cluster_alert_summary(cluster) if hydrate_live_signals else None
        active_alerts = alert_summary['active'] if alert_summary is not None else None
        critical_alerts = alert_summary['critical'] if alert_summary is not None else 0
        warning_alerts = alert_summary['warning'] if alert_summary is not None else 0
        alerts_status = 'Live' if alert_summary is not None else 'Unavailable'

        status = _derive_cluster_status(
            cluster,
            nodes_total=nodes_total,
            not_ready_nodes=not_ready,
            unhealthy_pods=unhealthy_pods,
            live_nodes_available=nodes_status == 'Live',
            active_alerts=active_alerts or 0,
            critical_alerts=critical_alerts,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
        )
        status_reason = _derive_cluster_status_reason(
            cluster,
            nodes_total=nodes_total,
            not_ready_nodes=not_ready,
            unhealthy_pods=unhealthy_pods,
            live_nodes_available=nodes_status == 'Live',
            active_alerts=active_alerts or 0,
            critical_alerts=critical_alerts,
            warning_alerts=warning_alerts,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
        )
        last_sync = latest_timestamp([*nodes, *pods]) or coerce_datetime(
            get_attr(cluster, 'last_check', 'updated_at', 'created_at')
        )

        endpoint = str(get_attr(cluster, 'server', default='') or '').strip()
        if not endpoint:
            endpoint = 'Endpoint not detected'

        rows.append(
            ClusterHealthRow(
                cluster_id=cluster_id,
                cluster_name=str(get_attr(cluster, 'name', default='Unnamed Cluster')),
                cluster_endpoint=endpoint,
                status=status,
                status_reason=status_reason,
                nodes_ready=nodes_ready,
                nodes_total=nodes_total,
                nodes_status=nodes_status,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                cpu_status=cpu_status,
                memory_status=memory_status,
                active_alerts=active_alerts,
                alerts_status=alerts_status,
                last_sync=human_time(last_sync) if last_sync else 'No sync yet',
            )
        )

    return rows


def _get_cluster_live_signal_snapshot(cluster: Any) -> dict[str, float | int | None] | None:
    try:
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        utilization = UtilizationService(PrometheusService(cluster))
        return {
            'cpu': safe_optional_float(utilization.get_cpu_utilization()),
            'memory': safe_optional_float(utilization.get_memory_utilization()),
            'nodes_total': safe_optional_int(utilization.get_total_nodes()),
            'nodes_ready': safe_optional_int(utilization.get_ready_nodes()),
        }
    except Exception:
        return None


def _get_cluster_alert_summary(cluster: Any) -> dict[str, int] | None:
    try:
        from app.analytics.alerts.service import load_alerts_by_source

        alerts, source_status = load_alerts_by_source(cluster=cluster, source='auto')
        if not source_status.get('connected'):
            return None

        active_alerts = [
            item for item in alerts if str(item.get('status', 'active')).lower() in {'active', 'firing', 'pending'}
        ]

        return {
            'active': len(active_alerts),
            'critical': sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'critical'),
            'warning': sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'warning'),
        }
    except Exception:
        return None


def _derive_cluster_status(
    cluster: Any,
    *,
    nodes_total: int,
    not_ready_nodes: int,
    unhealthy_pods: int,
    live_nodes_available: bool,
    active_alerts: int,
    critical_alerts: int,
    cpu_percent: float | None,
    memory_percent: float | None,
) -> str:
    raw_status = normalize_status(get_attr(cluster, 'status', 'connection_status', 'health', default=''))

    if not live_nodes_available:
        if critical_alerts > 0:
            return 'Critical'
        if active_alerts > 0 or unhealthy_pods > 0:
            return 'Warning'
        return 'Unknown'
    if raw_status in {'offline', 'failed', 'unreachable', 'critical'}:
        return 'Critical'
    if critical_alerts > 0:
        return 'Critical'
    if not_ready_nodes >= max(1, nodes_total // 2):
        return 'Critical'
    if safe_float(cpu_percent) >= 90 or safe_float(memory_percent) >= 90:
        return 'Critical'
    if not_ready_nodes > 0:
        return 'Warning'
    if unhealthy_pods > 0:
        return 'Warning'
    if active_alerts > 0:
        return 'Warning'
    if safe_float(cpu_percent) >= 75 or safe_float(memory_percent) >= 75:
        return 'Warning'
    if raw_status in {'warning', 'degraded'}:
        return 'Warning'
    return 'Healthy'


def _derive_cluster_status_reason(
    cluster: Any,
    *,
    nodes_total: int,
    not_ready_nodes: int,
    unhealthy_pods: int,
    live_nodes_available: bool,
    active_alerts: int,
    critical_alerts: int,
    warning_alerts: int,
    cpu_percent: float | None,
    memory_percent: float | None,
) -> str:
    raw_status = normalize_status(get_attr(cluster, 'status', 'connection_status', 'health', default=''))

    if not live_nodes_available:
        if critical_alerts > 0:
            return f'{critical_alerts} critical alert{plural_suffix(critical_alerts)} detected; Prometheus node signal unavailable'  # noqa: E501
        if active_alerts > 0:
            return f'{active_alerts} active alert{plural_suffix(active_alerts)} detected; Prometheus node signal unavailable'
        return 'Prometheus node signal unavailable'
    if raw_status in {'offline', 'failed', 'unreachable', 'critical'}:
        return f'Cluster connection status is {raw_status}'
    if critical_alerts > 0:
        return f'{critical_alerts} critical alert{plural_suffix(critical_alerts)} detected'
    if not_ready_nodes >= max(1, nodes_total // 2):
        return f'{not_ready_nodes} of {nodes_total} nodes are NotReady'
    if safe_float(cpu_percent) >= 90:
        return f'CPU utilization is {safe_float(cpu_percent):.1f}%'
    if safe_float(memory_percent) >= 90:
        return f'Memory utilization is {safe_float(memory_percent):.1f}%'
    if not_ready_nodes > 0:
        return f'{not_ready_nodes} node{plural_suffix(not_ready_nodes)} NotReady'
    if unhealthy_pods > 0:
        return f'{unhealthy_pods} unhealthy pod{plural_suffix(unhealthy_pods)} detected'
    if active_alerts > 0:
        if warning_alerts > 0:
            return f'{warning_alerts} warning alert{plural_suffix(warning_alerts)} detected'
        return f'{active_alerts} active alert{plural_suffix(active_alerts)} detected'
    if safe_float(cpu_percent) >= 75:
        return f'CPU utilization is {safe_float(cpu_percent):.1f}%'
    if safe_float(memory_percent) >= 75:
        return f'Memory utilization is {safe_float(memory_percent):.1f}%'
    if raw_status in {'warning', 'degraded'}:
        return f'Cluster status is {raw_status} in database'
    return 'No issue detected'
