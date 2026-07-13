from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from importlib import import_module
from typing import Any
from urllib.parse import quote

from app.dashboard.schema import (
    AlertItem,
    AlertsSnapshot,
    CapacityItem,
    CapacitySnapshot,
    ClusterHealthPagination,
    ClusterHealthRow,
    ConsumerItem,
    DashboardClusterOption,
    DashboardKpi,
    DashboardOverview,
    ForecastItem,
    ForecastSnapshot,
    FreshnessItem,
    InventorySnapshot,
    RecommendationItem,
    ReportingSnapshot,
    ReportItem,
    TopConsumersSnapshot,
)
from app.intelligence.recommendation_engine import build_dashboard_recommendations

try:
    from app.extensions import db
except Exception:  # pragma: no cover
    try:
        from app.extensions.db import db  # type: ignore[no-redef]
    except Exception:
        db = None  # type: ignore[assignment]


def get_dashboard_overview(
    selected_cluster_id: str | None = None,
    cluster_health_page: str | int | None = 1,
    *,
    hydrate_live_sections: bool = True,
    live_sections: Iterable[str] | None = None,
) -> DashboardOverview:
    models = _load_models()

    Cluster = models.get('Cluster')
    NodeInventory = models.get('NodeInventory')
    NamespaceInventory = models.get('NamespaceInventory')
    WorkloadInventory = models.get('WorkloadInventory')
    PodInventory = models.get('PodInventory')
    ServiceInventory = models.get('ServiceInventory')
    IngressInventory = models.get('IngressInventory')
    StorageInventory = models.get('StorageInventory')

    live_section_set = {str(section) for section in (live_sections or [])}

    def should_hydrate(*section_names: str) -> bool:
        if not hydrate_live_sections:
            return False
        if not live_section_set:
            return True
        return any(section_name in live_section_set for section_name in section_names)

    clusters_raw = _query_all(Cluster) if Cluster else []
    clusters = [
        DashboardClusterOption(
            id=str(_get_attr(cluster, 'id', default='')),
            name=str(_get_attr(cluster, 'name', default='Unnamed Cluster')),
        )
        for cluster in clusters_raw
    ]

    selected_cluster_id = _normalize_selected_cluster(selected_cluster_id, clusters)
    live_cluster = _get_live_cluster(clusters_raw=clusters_raw, selected_cluster_id=selected_cluster_id)

    nodes = _query_all(NodeInventory, selected_cluster_id) if NodeInventory else []
    namespaces = _query_all(NamespaceInventory, selected_cluster_id) if NamespaceInventory else []
    workloads = _query_all(WorkloadInventory, selected_cluster_id) if WorkloadInventory else []
    pods = _query_all(PodInventory, selected_cluster_id) if PodInventory else []
    services = _query_all(ServiceInventory, selected_cluster_id) if ServiceInventory else []
    ingresses = _query_all(IngressInventory, selected_cluster_id) if IngressInventory else []
    storage_items = _query_all(StorageInventory, selected_cluster_id) if StorageInventory else []

    capacity_snapshot = (
        _build_capacity_snapshot(live_cluster=live_cluster, selected_cluster_id=selected_cluster_id)
        if should_hydrate('capacity', 'capacity_snapshot', 'kpi_cards', 'data_freshness', 'recommended_actions', 'hero')
        else _empty_capacity_snapshot(insight='Live capacity snapshot will load after the dashboard shell is ready.')
    )
    alerts_snapshot = (
        _build_alerts_snapshot(live_cluster=live_cluster)
        if should_hydrate('alerts', 'alerts_summary', 'kpi_cards', 'data_freshness', 'recommended_actions', 'hero')
        else _alerts_snapshot_with_message('Live alert snapshot will load after the dashboard shell is ready.')
    )
    top_consumers_snapshot = (
        _build_top_consumers_snapshot(live_cluster=live_cluster)
        if should_hydrate('top_consumers', 'data_freshness')
        else _top_consumers_snapshot_with_message('Top consumer snapshot will load after the dashboard shell is ready.')
    )
    forecast_snapshot = (
        _build_forecast_snapshot(live_cluster=live_cluster)
        if should_hydrate('forecast', 'forecast_risk', 'data_freshness')
        else ForecastSnapshot(
            items=_default_forecast_items('Pending', 'Waiting for trend snapshot'),
            insight='Forecast snapshot will load after the dashboard shell is ready.',
            source_status='Unavailable',
        )
    )
    reporting_snapshot = _build_reporting_snapshot(selected_cluster_id=selected_cluster_id)

    nodes_total = len(nodes)
    nodes_ready = sum(1 for node in nodes if _is_ready_node(node))
    not_ready_nodes = max(nodes_total - nodes_ready, 0)

    running_pods = sum(
        1 for pod in pods if _normalize_status(_get_attr(pod, 'status', 'phase', default='')) == 'running'
    )
    unhealthy_pods = sum(1 for pod in pods if _is_unhealthy_pod(pod))

    active_alerts = alerts_snapshot.critical + alerts_snapshot.warning + alerts_snapshot.info
    active_alerts_label = str(active_alerts) if live_cluster is not None else 'N/A'
    active_alerts_description = (
        f'{alerts_snapshot.critical} Critical • {alerts_snapshot.warning} Warning'
        if live_cluster is not None
        else 'Select a cluster to view live alert signals'
    )
    has_prometheus_data = (
        capacity_snapshot.source_status == 'Available'
        or top_consumers_snapshot.source_status == 'Available'
        or forecast_snapshot.source_status == 'Available'
    )
    has_alertmanager_data = alerts_snapshot.source_status == 'Available'

    clusters_for_health = clusters_raw
    if selected_cluster_id:
        clusters_for_health = [
            cluster for cluster in clusters_raw if str(_get_attr(cluster, 'id', default='')) == selected_cluster_id
        ]

    health_clusters_page, cluster_health_pagination = _paginate_sequence(
        items=clusters_for_health,
        page=cluster_health_page,
        per_page=5,
    )
    cluster_health = _build_cluster_health(
        clusters_raw=health_clusters_page,
        selected_cluster_id=None,
        NodeInventory=NodeInventory,
        PodInventory=PodInventory,
        live_cluster=live_cluster,
        capacity_snapshot=capacity_snapshot,
        alerts_snapshot=alerts_snapshot,
        hydrate_live_signals=should_hydrate('cluster_health'),
    )

    inventory_snapshot = InventorySnapshot(
        namespaces=len(namespaces),
        workloads=len(workloads),
        pods=len(pods),
        services=len(services),
        ingresses=len(ingresses),
        storage=len(storage_items),
        running_pods=running_pods,
        unhealthy_pods=unhealthy_pods,
    )

    kpis = [
        DashboardKpi(
            label='Clusters',
            value=str(len(clusters)),
            description=f"{_count_cluster_status(clusters_raw, 'healthy')} healthy • {_count_cluster_status(clusters_raw, 'warning')} warning",  # noqa: E501
            icon='network',
            tone='blue',
        ),
        DashboardKpi(
            label='Nodes',
            value=str(nodes_total),
            description=f'{nodes_ready} Ready • {not_ready_nodes} NotReady',
            icon='server',
            tone='emerald' if not_ready_nodes == 0 else 'amber',
        ),
        DashboardKpi(
            label='Namespaces',
            value=str(len(namespaces)),
            description='Discovered Kubernetes namespaces',
            icon='layout-grid',
            tone='violet',
        ),
        DashboardKpi(
            label='Workloads',
            value=str(len(workloads)),
            description='Deployments, StatefulSets, DaemonSets, Jobs, CronJobs',
            icon='boxes',
            tone='blue',
        ),
        DashboardKpi(
            label='Pods',
            value=str(len(pods)),
            description=f'{running_pods} Running • {unhealthy_pods} need attention',
            icon='container',
            tone='emerald' if unhealthy_pods == 0 else 'amber',
        ),
        DashboardKpi(
            label='CPU Usage',
            value=_percent_label(_capacity_percent(capacity_snapshot, 'CPU')) if live_cluster is not None else 'N/A',
            description=(
                _kpi_metric_description(live_cluster, 'Current usage snapshot')
                if live_cluster is not None
                else 'Select a cluster to view live Prometheus CPU usage'
            ),
            icon='cpu',
            tone='orange' if live_cluster is not None else 'slate',
        ),
        DashboardKpi(
            label='Memory Usage',
            value=_percent_label(_capacity_percent(capacity_snapshot, 'Memory')) if live_cluster is not None else 'N/A',
            description=(
                _kpi_metric_description(live_cluster, 'Current usage snapshot')
                if live_cluster is not None
                else 'Select a cluster to view live Prometheus memory usage'
            ),
            icon='memory-stick',
            tone='violet' if live_cluster is not None else 'slate',
        ),
        DashboardKpi(
            label='Active Alerts',
            value=active_alerts_label,
            description=active_alerts_description,
            icon='bell-ring',
            tone='red' if alerts_snapshot.critical else 'amber' if alerts_snapshot.warning else 'emerald',
        ),
    ]

    latest_sync = _latest_timestamp([*nodes, *pods, *workloads, *namespaces, *services, *ingresses, *storage_items])
    last_updated = _human_time(latest_sync) if latest_sync else 'Just now'

    data_freshness = _build_data_freshness(
        latest_inventory_sync=latest_sync,
        has_prometheus_data=has_prometheus_data,
        has_alertmanager_data=has_alertmanager_data,
        reporting_snapshot=reporting_snapshot,
        live_cluster=live_cluster,
    )

    recommendation_cards = (
        build_dashboard_recommendations(selected_cluster_id=selected_cluster_id)
        if should_hydrate('recommended_actions')
        else []
    )
    recommendations = [
        RecommendationItem(
            title=str(card.get('title') or 'Review recommendation'),
            description=str(
                card.get('recommended_action')
                or card.get('summary')
                or 'Review the active finding in Intelligence > Recommendations.'
            ),
            category=str(card.get('category_label') or card.get('category') or 'Operations'),
            severity=str(card.get('severity') or 'info'),
            icon=_recommendation_icon(card),
            href=_recommendation_href(card),
            priority=str(card.get('priority') or 'P3'),
            source=str(card.get('signal_source_label') or card.get('signal_source') or 'Intelligence engine'),
            rule_key=str(card.get('rule_key') or ''),
        )
        for card in recommendation_cards
    ]

    hero_integration_meta = _build_hero_integration_meta(
        live_cluster=live_cluster,
        capacity_snapshot=capacity_snapshot,
        alerts_snapshot=alerts_snapshot,
    )

    return DashboardOverview(
        clusters=clusters,
        selected_cluster_id=selected_cluster_id,
        last_updated=last_updated,
        global_kpis=kpis,
        cluster_health_snapshot=cluster_health,
        cluster_health_pagination=cluster_health_pagination,
        capacity_snapshot=capacity_snapshot,
        alerts_snapshot=alerts_snapshot,
        top_consumers_snapshot=top_consumers_snapshot,
        forecast_snapshot=forecast_snapshot,
        inventory_snapshot=inventory_snapshot,
        reporting_snapshot=reporting_snapshot,
        data_freshness=data_freshness,
        recommended_actions=recommendations,
        meta={'generated_at': datetime.now(UTC).isoformat(), **hero_integration_meta},
    )


def _normalize_page_number(value: str | int | None) -> int:
    try:
        page = int(value or 1)
    except (TypeError, ValueError):
        return 1

    return max(page, 1)


def _paginate_sequence(
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


def _load_models() -> dict[str, Any]:
    model_specs = {
        'Cluster': (('app.models.cluster', 'Cluster'), ('app.models', 'Cluster')),
        'NodeInventory': (('app.models.inventory', 'NodeInventory'), ('app.models', 'NodeInventory')),
        'NamespaceInventory': (('app.models.inventory', 'NamespaceInventory'), ('app.models', 'NamespaceInventory')),
        'WorkloadInventory': (('app.models.inventory', 'WorkloadInventory'), ('app.models', 'WorkloadInventory')),
        'PodInventory': (('app.models.inventory', 'PodInventory'), ('app.models', 'PodInventory')),
        'ServiceInventory': (('app.models.inventory', 'ServiceInventory'), ('app.models', 'ServiceInventory')),
        'IngressInventory': (('app.models.inventory', 'IngressInventory'), ('app.models', 'IngressInventory')),
        'StorageInventory': (('app.models.inventory', 'StorageInventory'), ('app.models', 'StorageInventory')),
        'GeneratedReport': (('app.models.report', 'Report'), ('app.models', 'Report')),
        'ReportTemplate': (('app.models.report', 'ReportTemplate'), ('app.models', 'ReportTemplate')),
        'ReportSchedule': (('app.models.report', 'ReportSchedule'), ('app.models', 'ReportSchedule')),
    }

    loaded: dict[str, Any] = {}
    for public_name, candidates in model_specs.items():
        for module_name, attr_name in candidates:
            try:
                module = import_module(module_name)
                loaded[public_name] = getattr(module, attr_name)
                break
            except Exception:
                continue
    return loaded


def _query_all(model: Any, cluster_id: str | None = None, limit: int | None = None) -> list[Any]:
    if model is None:
        return []

    try:
        query = db.session.query(model) if db is not None else model.query

        if cluster_id and hasattr(model, 'cluster_id'):
            query = query.filter(getattr(model, 'cluster_id') == cluster_id)

        order_col = _first_model_column(
            model, ['updated_at', 'collected_at', 'created_at', 'generated_at', 'last_check']
        )
        if order_col is not None:
            query = query.order_by(order_col.desc())

        if limit is not None:
            query = query.limit(limit)

        return list(query.all())
    except Exception:
        return []


def _count(model: Any, cluster_id: str | None = None) -> int:
    if model is None:
        return 0
    try:
        query = db.session.query(model) if db is not None else model.query
        if cluster_id and hasattr(model, 'cluster_id'):
            query = query.filter(getattr(model, 'cluster_id') == cluster_id)
        return int(query.count())
    except Exception:
        return 0


def _first_model_column(model: Any, names: list[str]) -> Any | None:
    for name in names:
        if hasattr(model, name):
            return getattr(model, name)
    return None


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _normalize_selected_cluster(selected_cluster_id: str | None, clusters: list[DashboardClusterOption]) -> str | None:
    if not selected_cluster_id:
        return None
    valid_ids = {cluster.id for cluster in clusters}
    return selected_cluster_id if selected_cluster_id in valid_ids else None


def _get_live_cluster(*, clusters_raw: list[Any], selected_cluster_id: str | None) -> Any | None:
    if not selected_cluster_id:
        return None

    for cluster in clusters_raw:
        if str(_get_attr(cluster, 'id', default='')) == selected_cluster_id:
            return cluster

    return None


def _normalize_status(value: Any) -> str:
    return str(value or '').strip().lower()


def _is_ready_node(node: Any) -> bool:
    status = _normalize_status(_get_attr(node, 'status', 'condition', 'ready', default=''))
    return status in {'ready', 'true', 'active', 'healthy'}


def _is_unhealthy_pod(pod: Any) -> bool:
    status = _normalize_status(_get_attr(pod, 'status', 'phase', default=''))
    return status in {'pending', 'failed', 'unknown', 'crashloopbackoff', 'imagepullbackoff', 'error'}


def _build_cluster_health(
    *,
    clusters_raw: list[Any],
    selected_cluster_id: str | None,
    NodeInventory: Any,
    PodInventory: Any,
    live_cluster: Any | None,
    capacity_snapshot: CapacitySnapshot,
    alerts_snapshot: AlertsSnapshot,
    hydrate_live_signals: bool = True,
) -> list[ClusterHealthRow]:
    rows: list[ClusterHealthRow] = []
    clusters = clusters_raw

    if selected_cluster_id:
        clusters = [
            cluster for cluster in clusters_raw if str(_get_attr(cluster, 'id', default='')) == selected_cluster_id
        ]

    for cluster in clusters:
        cluster_id = str(_get_attr(cluster, 'id', default=''))
        nodes = _query_all(NodeInventory, cluster_id) if NodeInventory else []
        pods = _query_all(PodInventory, cluster_id) if PodInventory else []

        inventory_nodes_total = len(nodes)
        inventory_nodes_ready = sum(1 for node in nodes if _is_ready_node(node))
        unhealthy_pods = sum(1 for pod in pods if _is_unhealthy_pod(pod))

        live_signals = _get_cluster_live_signal_snapshot(cluster) if hydrate_live_signals else None
        cpu_percent = live_signals.get('cpu') if live_signals else None
        memory_percent = live_signals.get('memory') if live_signals else None
        live_nodes_total = _safe_optional_int(live_signals.get('nodes_total')) if live_signals else None
        live_nodes_ready = _safe_optional_int(live_signals.get('nodes_ready')) if live_signals else None
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
        last_sync = _latest_timestamp([*nodes, *pods]) or _coerce_datetime(
            _get_attr(cluster, 'last_check', 'updated_at', 'created_at')
        )

        endpoint = str(_get_attr(cluster, 'server', default='') or '').strip()
        if not endpoint:
            endpoint = 'Endpoint not detected'

        rows.append(
            ClusterHealthRow(
                cluster_id=cluster_id,
                cluster_name=str(_get_attr(cluster, 'name', default='Unnamed Cluster')),
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
                last_sync=_human_time(last_sync) if last_sync else 'No sync yet',
            )
        )

    return rows


def _get_cluster_live_signal_snapshot(cluster: Any) -> dict[str, float | int | None] | None:
    try:
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        utilization = UtilizationService(PrometheusService(cluster))
        return {
            'cpu': _safe_optional_float(utilization.get_cpu_utilization()),
            'memory': _safe_optional_float(utilization.get_memory_utilization()),
            'nodes_total': _safe_optional_int(utilization.get_total_nodes()),
            'nodes_ready': _safe_optional_int(utilization.get_ready_nodes()),
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
    raw_status = _normalize_status(_get_attr(cluster, 'status', 'connection_status', 'health', default=''))

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
    if _safe_float(cpu_percent) >= 90 or _safe_float(memory_percent) >= 90:
        return 'Critical'
    if not_ready_nodes > 0:
        return 'Warning'
    if unhealthy_pods > 0:
        return 'Warning'
    if active_alerts > 0:
        return 'Warning'
    if _safe_float(cpu_percent) >= 75 or _safe_float(memory_percent) >= 75:
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
    raw_status = _normalize_status(_get_attr(cluster, 'status', 'connection_status', 'health', default=''))

    if not live_nodes_available:
        if critical_alerts > 0:
            return f'{critical_alerts} critical alert{_plural(critical_alerts)} detected; Prometheus node signal unavailable'  # noqa: E501
        if active_alerts > 0:
            return f'{active_alerts} active alert{_plural(active_alerts)} detected; Prometheus node signal unavailable'
        return 'Prometheus node signal unavailable'
    if raw_status in {'offline', 'failed', 'unreachable', 'critical'}:
        return f'Cluster connection status is {raw_status}'
    if critical_alerts > 0:
        return f'{critical_alerts} critical alert{_plural(critical_alerts)} detected'
    if not_ready_nodes >= max(1, nodes_total // 2):
        return f'{not_ready_nodes} of {nodes_total} nodes are NotReady'
    if _safe_float(cpu_percent) >= 90:
        return f'CPU utilization is {_safe_float(cpu_percent):.1f}%'
    if _safe_float(memory_percent) >= 90:
        return f'Memory utilization is {_safe_float(memory_percent):.1f}%'
    if not_ready_nodes > 0:
        return f'{not_ready_nodes} node{_plural(not_ready_nodes)} NotReady'
    if unhealthy_pods > 0:
        return f'{unhealthy_pods} unhealthy pod{_plural(unhealthy_pods)} detected'
    if active_alerts > 0:
        if warning_alerts > 0:
            return f'{warning_alerts} warning alert{_plural(warning_alerts)} detected'
        return f'{active_alerts} active alert{_plural(active_alerts)} detected'
    if _safe_float(cpu_percent) >= 75:
        return f'CPU utilization is {_safe_float(cpu_percent):.1f}%'
    if _safe_float(memory_percent) >= 75:
        return f'Memory utilization is {_safe_float(memory_percent):.1f}%'
    if raw_status in {'warning', 'degraded'}:
        return f'Cluster status is {raw_status} in database'
    return 'No issue detected'


def _recommendation_icon(card: dict[str, Any]) -> str:
    return {
        'node': 'server-crash',
        'pod': 'container',
        'workload': 'boxes',
        'namespace': 'layout-grid',
        'persistent_volume': 'hard-drive',
        'tls_secret': 'shield-check',
        'cluster': 'gauge',
    }.get(str(card.get('source_kind') or ''), 'sparkles')


def _recommendation_href(card: dict[str, Any]) -> str:
    rule_key = str(card.get('rule_key') or '').strip()
    if not rule_key:
        return '/intelligence/recommendations'
    return f'/intelligence/recommendations?q={quote(rule_key, safe="")}'


def _plural(value: int) -> str:
    return '' if value == 1 else 's'


def _count_cluster_status(clusters_raw: list[Any], expected: str) -> int:
    count = 0
    for cluster in clusters_raw:
        status = _normalize_status(_get_attr(cluster, 'status', 'connection_status', 'health', default=''))
        if expected == 'healthy' and status in {'active', 'connected', 'healthy', 'online', ''}:
            count += 1
        elif expected == 'warning' and status in {'warning', 'degraded'}:
            count += 1
    return count


def _build_capacity_snapshot(*, live_cluster: Any | None, selected_cluster_id: str | None) -> CapacitySnapshot:
    if live_cluster is None:
        return _empty_capacity_snapshot(
            insight='Select a specific cluster to show worker-node capacity and headroom from Prometheus.'
            if not selected_cluster_id
            else 'Selected cluster is not available for live worker capacity metrics.'
        )

    try:
        from app.analytics.capacity.service import CapacityService
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        prometheus = PrometheusService(live_cluster)
        capacity_service = CapacityService(UtilizationService(prometheus))
        summary = capacity_service.get_capacity_summary_from_summary({})
    except Exception as exc:
        return _empty_capacity_snapshot(insight=f'Prometheus worker capacity snapshot unavailable: {exc}')

    cpu = _worker_capacity_item(
        label='CPU',
        section=summary.get('cpu', {}),
        unit='cores',
        digits=2,
    )
    memory = _worker_capacity_item(
        label='Memory',
        section=summary.get('memory', {}),
        unit='GiB',
        digits=2,
    )
    pods = _worker_capacity_item(
        label='Pod Capacity',
        section=summary.get('pods', {}),
        unit='pods',
        digits=0,
    )
    items = [cpu, memory, pods]

    measured_items = [item for item in items if item.used_percent is not None]
    highest = max(measured_items, key=lambda item: _safe_float(item.used_percent), default=None)
    risk = _risk_from_percent(_safe_float(highest.used_percent)) if highest is not None else 'Unknown'
    insight = _capacity_insight(risk, items)
    risk_detail, recommended_action = _capacity_risk_guidance(risk, highest)

    return CapacitySnapshot(
        items=items,
        risk=risk,
        insight=insight,
        risk_detail=risk_detail,
        recommended_action=recommended_action,
        source_status='Available',
    )


def _worker_capacity_item(
    *,
    label: str,
    section: dict[str, Any],
    unit: str,
    digits: int,
) -> CapacityItem:
    capacity = _safe_float(section.get('capacity'))
    used = _safe_float(section.get('used'))
    headroom = _safe_optional_float(section.get('headroom')) if capacity > 0 else None
    used_percent = max(0.0, min(100.0, 100.0 - headroom)) if headroom is not None else None

    if digits == 0:
        description = f'{int(round(used))} / {int(round(capacity))} {unit} on worker nodes'
    else:
        description = f'{used:.{digits}f} / {capacity:.{digits}f} worker allocatable {unit}'

    return CapacityItem(
        label=label,
        used_percent=round(used_percent, 2) if used_percent is not None else None,
        headroom_percent=round(headroom, 2) if headroom is not None else None,
        description=description,
    )


def _empty_capacity_snapshot(*, insight: str) -> CapacitySnapshot:
    return CapacitySnapshot(
        items=[
            CapacityItem(label='CPU', used_percent=None, headroom_percent=None, description='Worker metric unavailable'),
            CapacityItem(
                label='Memory', used_percent=None, headroom_percent=None, description='Worker metric unavailable'
            ),
            CapacityItem(
                label='Pod Capacity', used_percent=None, headroom_percent=None, description='Worker metric unavailable'
            ),
        ],
        risk='Unknown',
        insight=insight,
        risk_detail='Overall worker capacity risk cannot be calculated because one or more required metrics are unavailable.',
        recommended_action='Verify the selected cluster Prometheus connection and kube-state-metrics node-role labels, then reload the snapshot.',
        source_status='Unavailable',
    )


def _capacity_risk_guidance(
    risk: str,
    highest: CapacityItem | None,
) -> tuple[str, str]:
    resource = highest.label if highest is not None else 'Worker capacity'
    utilization = _safe_float(highest.used_percent) if highest is not None else 0.0

    if risk == 'Critical':
        return (
            f'{resource} utilization is {utilization:.0f}%, leaving almost no worker-node scheduling buffer. '
            'New pods may remain Pending and existing workloads may face eviction or performance degradation.',
            'Review Capacity Analysis and Top Consumers immediately, reduce avoidable load, and add or resize worker capacity before the remaining headroom is exhausted.',
        )
    if risk == 'High':
        return (
            f'{resource} utilization is {utilization:.0f}%. Worker-node headroom is limited and sustained growth can affect scheduling reliability.',
            'Review top consumers, requests and limits, forecast trend, and pending workloads. Prepare scaling or workload optimization before utilization reaches the critical threshold.',
        )
    if risk == 'Medium':
        return (
            f'{resource} utilization is {utilization:.0f}%. Capacity remains usable, but the operational buffer is narrowing.',
            'Validate workload requests and limits, monitor the growth trend, and confirm that planned deployments fit within current worker headroom.',
        )
    if risk == 'Low':
        return (
            f'{resource} is the highest worker-node signal at {utilization:.0f}%, with sufficient headroom for current demand.',
            'No immediate scaling action is required. Continue monitoring trends and keep workload requests, limits, and capacity baselines current.',
        )
    return (
        'Worker capacity risk is unknown because the required utilization or allocatable metrics are incomplete.',
        'Verify Prometheus, kube-state-metrics, and node-role labels before making scaling or placement decisions.',
    )


def _alerts_snapshot_with_message(
    message: str,
    *,
    source_status: str = 'Unavailable',
) -> AlertsSnapshot:
    snapshot = AlertsSnapshot()
    snapshot.source_status = source_status
    snapshot.message = message
    return snapshot


def _top_consumers_snapshot_with_message(
    message: str,
    *,
    source_status: str = 'Unavailable',
) -> TopConsumersSnapshot:
    snapshot = TopConsumersSnapshot()
    snapshot.source_status = source_status
    snapshot.message = message
    return snapshot


def _build_alerts_snapshot(*, live_cluster: Any | None) -> AlertsSnapshot:
    if live_cluster is None:
        return _alerts_snapshot_with_message(
            'Select a specific cluster to load AlertManager or Prometheus alert snapshots.'
        )

    try:
        from app.analytics.alerts.service import load_alerts_by_source

        alerts, source_status = load_alerts_by_source(cluster=live_cluster, source='auto')
    except Exception as exc:
        return _alerts_snapshot_with_message(f'Alert snapshot unavailable: {exc}')

    active_alerts = [
        item for item in alerts if str(item.get('status', 'active')).lower() in {'active', 'firing', 'pending'}
    ]
    critical = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'critical')
    warning = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() == 'warning')
    info = sum(1 for item in active_alerts if str(item.get('severity', '')).lower() in {'info', 'none', ''})

    snapshot_items = []
    for item in active_alerts[:3]:
        name = str(item.get('name') or item.get('alertname') or 'Unknown Alert')
        namespace = str(item.get('namespace') or '-')
        target = str(item.get('target') or '-')
        description = str(item.get('summary') or item.get('description') or f'{namespace} / {target}')
        snapshot_items.append(
            AlertItem(
                title=name,
                description=description,
                severity=str(item.get('severity') or 'none').title(),
                age=str(item.get('starts_at_display') or item.get('starts_at') or ''),
            )
        )

    connected = bool(source_status.get('connected'))
    resolved_source = str(source_status.get('resolved_source') or source_status.get('source') or 'alert source')

    snapshot = AlertsSnapshot()
    snapshot.critical = critical
    snapshot.warning = warning
    snapshot.info = info
    snapshot.items = snapshot_items
    snapshot.source_status = 'Available' if connected or active_alerts else 'Unavailable'
    snapshot.message = (
        f'Loaded from {resolved_source.title()}.'
        if connected
        else str(source_status.get('error') or 'Alert source unavailable.')
    )
    return snapshot


def _build_top_consumers_snapshot(*, live_cluster: Any | None) -> TopConsumersSnapshot:
    if live_cluster is None:
        return _top_consumers_snapshot_with_message('Select a specific cluster to load top consumer snapshots.')

    try:
        from app.analytics.top_consumers.service import TopConsumersService
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        utilization = UtilizationService(PrometheusService(live_cluster))
        service = TopConsumersService(utilization)
        payload = service.get_top_consumers_payload(
            selected_namespace='',
            selected_resource='all',
            selected_search='',
            selected_sort='usage_percent',
            selected_focus='',
            page=1,
            per_page=10,
        )
    except Exception as exc:
        return _top_consumers_snapshot_with_message(f'Top consumers snapshot unavailable: {exc}')

    rows = payload.get('all_rows') or payload.get('rows') or []
    if not isinstance(rows, list):
        rows = []

    cpu_rows = [row for row in rows if str(row.get('resource_type')) == 'cpu']
    memory_rows = [row for row in rows if str(row.get('resource_type')) == 'memory']

    insight = _build_top_consumers_insight(rows=rows, cpu_rows=cpu_rows, memory_rows=memory_rows)

    snapshot = TopConsumersSnapshot()
    snapshot.cpu = _consumer_items(cpu_rows[:3])
    snapshot.memory = _consumer_items(memory_rows[:3])
    snapshot.source_status = 'Available' if rows else 'Unavailable'
    snapshot.message = (
        'Top consumers loaded from Prometheus.'
        if rows
        else 'No top consumer rows returned by Prometheus.'
    )
    snapshot.insight_title = str(insight['title'])
    snapshot.insight_description = str(insight['description'])
    snapshot.insight_items = list(insight['items'])
    snapshot.missing_request_limit_count = int(insight['missing_request_limit_count'])
    snapshot.high_usage_count = int(insight['high_usage_count'])
    return snapshot


def _consumer_items(rows: list[dict[str, Any]]) -> list[ConsumerItem]:
    items: list[ConsumerItem] = []
    for index, row in enumerate(rows, start=1):
        request_value = _safe_optional_float(row.get('request')) or 0.0
        limit_value = _safe_optional_float(row.get('limit')) or 0.0
        raw_percent = _safe_optional_float(row.get('usage_percent'))

        has_denominator = request_value > 0 or limit_value > 0
        percent = raw_percent if has_denominator else None
        signal_state = _consumer_signal_state(row=row, percent=percent, has_denominator=has_denominator)
        signal_label = _consumer_signal_label(
            request_value=request_value,
            limit_value=limit_value,
            percent=percent,
            signal_state=signal_state,
        )

        items.append(
            ConsumerItem(
                rank=index,
                name=str(row.get('workload') or row.get('pod') or row.get('container') or '-'),
                namespace=str(row.get('namespace') or '-'),
                value=str(row.get('current_display') or row.get('value') or '-'),
                percent=percent,
                request_display=str(row.get('request_display') or '-'),
                limit_display=str(row.get('limit_display') or '-'),
                signal_label=signal_label,
                signal_state=signal_state,
            )
        )
    return items


def _consumer_signal_state(*, row: dict[str, Any], percent: float | None, has_denominator: bool) -> str:
    if not has_denominator or percent is None:
        return 'unknown'

    risk = row.get('risk')
    if isinstance(risk, dict):
        key = str(risk.get('key') or risk.get('level') or '').lower()
        if key in {'critical', 'warning', 'normal'}:
            return key

    if percent >= 90:
        return 'critical'
    if percent >= 75:
        return 'warning'
    return 'normal'


def _consumer_signal_label(
    *,
    request_value: float,
    limit_value: float,
    percent: float | None,
    signal_state: str,
) -> str:
    if request_value <= 0 and limit_value <= 0:
        return 'Usage only'
    if request_value <= 0:
        return 'No request'
    if limit_value <= 0:
        return 'No limit'
    if percent is None:
        return 'Unknown'
    if signal_state == 'critical':
        return 'Critical usage'
    if signal_state == 'warning':
        return 'Warning usage'
    return 'Within range'


def _build_top_consumers_insight(
    *,
    rows: list[dict[str, Any]],
    cpu_rows: list[dict[str, Any]],
    memory_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return {
            'title': 'Consumer insights',
            'description': 'No top consumer rows were returned by Prometheus for this cluster.',
            'items': ['Prometheus returned no CPU or memory consumer rows.'],
            'missing_request_limit_count': 0,
            'high_usage_count': 0,
        }

    cpu_memory_rows = [row for row in rows if str(row.get('resource_type') or '').lower() in {'cpu', 'memory'}]

    missing_request_limit = []
    high_usage = []
    namespaces: dict[str, int] = {}

    for row in cpu_memory_rows:
        request_value = _safe_optional_float(row.get('request')) or 0.0
        limit_value = _safe_optional_float(row.get('limit')) or 0.0
        percent = _safe_optional_float(row.get('usage_percent'))
        namespace = str(row.get('namespace') or '-')
        namespaces[namespace] = namespaces.get(namespace, 0) + 1

        if request_value <= 0 or limit_value <= 0:
            missing_request_limit.append(row)

        if percent is not None and percent >= 75 and (request_value > 0 or limit_value > 0):
            high_usage.append(row)

    top_cpu = cpu_rows[0] if cpu_rows else None
    top_memory = memory_rows[0] if memory_rows else None
    dominant_namespace = '-'
    if namespaces:
        dominant_namespace = max(namespaces.items(), key=lambda item: item[1])[0]

    insight_items: list[str] = []
    if top_cpu:
        insight_items.append(f"Highest CPU: {top_cpu.get('workload') or top_cpu.get('pod') or '-'}")
    if top_memory:
        insight_items.append(f"Highest Memory: {top_memory.get('workload') or top_memory.get('pod') or '-'}")
    if dominant_namespace != '-':
        insight_items.append(f'Dominant namespace: {dominant_namespace}')
    if missing_request_limit:
        insight_items.append(f'{len(missing_request_limit)} consumer row(s) missing request or limit context')
    if high_usage:
        insight_items.append(f'{len(high_usage)} consumer row(s) above 75% usage')

    if missing_request_limit:
        description = (
            f'{len(missing_request_limit)} CPU/memory consumer row(s) are missing request or limit context. '
            'Bars are intentionally muted for usage-only rows to avoid misleading risk signals.'
        )
    elif high_usage:
        description = (
            f'{len(high_usage)} CPU/memory consumer row(s) are above the warning threshold. '
            'Open Top Consumers for request, limit, and namespace-level detail.'
        )
    else:
        description = 'Top CPU and memory consumers are within normal range based on available request/limit context.'

    return {
        'title': 'Consumer insights',
        'description': description,
        'items': insight_items[:4],
        'missing_request_limit_count': len(missing_request_limit),
        'high_usage_count': len(high_usage),
    }


def _build_forecast_snapshot(*, live_cluster: Any | None) -> ForecastSnapshot:
    if live_cluster is None:
        return ForecastSnapshot(
            items=_default_forecast_items('Unknown', 'Select a cluster'),
            insight='Select a specific cluster to load compact forecast and growth risk snapshots.',
            source_status='Unavailable',
        )

    try:
        from app.analytics.forecast.service import ForecastAnalysisService
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        utilization = UtilizationService(PrometheusService(live_cluster))
        service = ForecastAnalysisService(utilization_service=utilization, cluster=live_cluster)
        payload = service.get_forecast_analysis(
            namespace='',
            history_window='30d',
            forecast_horizon='30d',
            resource='all',
        )
    except Exception as exc:
        return ForecastSnapshot(
            items=_default_forecast_items('Unknown', 'Forecast unavailable'),
            insight=f'Forecast snapshot unavailable: {exc}',
            source_status='Unavailable',
        )

    raw_items = payload.get('items', [])
    items: list[ForecastItem] = []
    if isinstance(raw_items, list):
        for item in raw_items[:4]:
            status = str(item.get('status_label') or item.get('status') or 'Unknown').title()
            projected = item.get('projected_percent')
            projection = (
                f'Projected {float(projected):.0f}% in 30 days'
                if isinstance(projected, int | float)
                else 'Projection unavailable'
            )
            items.append(
                ForecastItem(
                    label=str(item.get('label') or 'Resource'),
                    risk=status,
                    projection=projection,
                    icon=str(item.get('icon') or 'activity'),
                )
            )

    has_data = bool(payload.get('has_data')) and bool(items)
    return ForecastSnapshot(
        items=items or _default_forecast_items('Unknown', 'Insufficient data'),
        insight=_forecast_insight(payload)
        if has_data
        else str(payload.get('message') or 'Insufficient trend data for reliable forecasting.'),
        source_status='Available' if has_data else 'Unavailable',
    )


def _default_forecast_items(risk: str, projection: str) -> list[ForecastItem]:
    return [
        ForecastItem(label='CPU Growth', risk=risk, projection=projection, icon='cpu'),
        ForecastItem(label='Memory Growth', risk=risk, projection=projection, icon='memory-stick'),
        ForecastItem(label='Storage Growth', risk=risk, projection=projection, icon='hard-drive'),
        ForecastItem(label='Pod Growth', risk=risk, projection=projection, icon='container'),
    ]


def _build_reporting_snapshot(selected_cluster_id: str | None) -> ReportingSnapshot:
    models = _load_models()
    Report = models.get('GeneratedReport')
    ReportTemplate = models.get('ReportTemplate')
    ReportSchedule = models.get('ReportSchedule')

    reports = _query_all(Report, selected_cluster_id, limit=3) if Report else []
    latest: list[ReportItem] = []
    for report in reports:
        title = str(_get_attr(report, 'title', 'name', 'report_name', default='Generated Report'))
        status = str(_get_attr(report, 'status', default='unknown')).title()
        generated_at = _coerce_datetime(_get_attr(report, 'generated_at', 'created_at', 'updated_at'))
        latest.append(
            ReportItem(
                title=title, status=status, generated_at=_human_time(generated_at) if generated_at else 'Unknown time'
            )
        )

    return ReportingSnapshot(
        generated_reports=_count(Report, selected_cluster_id),
        templates=_count(ReportTemplate, None),
        schedules=_count(ReportSchedule, selected_cluster_id),
        latest_reports=latest,
        source_status='Available' if Report else 'Unavailable',
    )


def _build_hero_integration_meta(
    *,
    live_cluster: Any | None,
    capacity_snapshot: CapacitySnapshot,
    alerts_snapshot: AlertsSnapshot,
) -> dict[str, str]:
    if live_cluster is None:
        return {
            'prometheus_status_label': 'Per-cluster',
            'prometheus_status_description': 'Shown in Cluster Health rows',
            'prometheus_status_tone': 'blue',
            'alertmanager_status_label': 'Per-cluster',
            'alertmanager_status_description': 'Shown in Cluster Health rows',
            'alertmanager_status_tone': 'blue',
        }

    prometheus_available = capacity_snapshot.source_status == 'Available'
    alertmanager_available = alerts_snapshot.source_status == 'Available'

    return {
        'prometheus_status_label': 'Connected' if prometheus_available else 'Unavailable',
        'prometheus_status_description': 'Live metrics ready' if prometheus_available else 'Check Prometheus config',
        'prometheus_status_tone': 'green' if prometheus_available else 'slate',
        'alertmanager_status_label': 'Connected' if alertmanager_available else 'Unavailable',
        'alertmanager_status_description': 'Alert signals ready'
        if alertmanager_available
        else 'Check AlertManager source',
        'alertmanager_status_tone': 'green' if alertmanager_available else 'slate',
    }


def _build_data_freshness(
    *,
    latest_inventory_sync: datetime | None,
    has_prometheus_data: bool,
    has_alertmanager_data: bool,
    reporting_snapshot: ReportingSnapshot,
    live_cluster: Any | None,
) -> list[FreshnessItem]:
    selected_cluster_mode = live_cluster is not None

    prometheus_value = 'Connected' if has_prometheus_data else 'Unavailable'
    prometheus_description = (
        'Live nodes, CPU, memory, capacity, top consumers, and forecast are available for the selected cluster.'
    )

    if not selected_cluster_mode:
        prometheus_value = 'Per-cluster in health table'
        prometheus_description = (
            'All Clusters mode checks Prometheus per cluster only for Cluster Health rows. '
            'Select one cluster to enable detailed live capacity, top consumers, and forecast blocks.'
        )
    elif not has_prometheus_data:
        prometheus_description = (
            'Prometheus is not configured, unreachable, or returned no usable metrics for the selected cluster.'
        )

    alertmanager_value = 'Connected' if has_alertmanager_data else 'Unavailable'
    alertmanager_description = 'AlertManager or Prometheus alert fallback is available for the selected cluster.'

    if not selected_cluster_mode:
        alertmanager_value = 'Per-cluster in health table'
        alertmanager_description = (
            'All Clusters mode checks alert availability per cluster only for Cluster Health rows. '
            'Select one cluster to inspect alert details and alert source context.'
        )
    elif not has_alertmanager_data:
        alertmanager_description = 'AlertManager is not configured, unreachable, or Prometheus alert fallback is unavailable for the selected cluster.'  # noqa: E501

    return [
        FreshnessItem(
            label='Inventory Sync',
            status='Healthy' if latest_inventory_sync else 'Unknown',
            value=_human_time(latest_inventory_sync) if latest_inventory_sync else 'No sync yet',
            icon='refresh-cw',
            description='Database inventory and report summaries use the latest collected snapshot for the selected dashboard scope.',  # noqa: E501
        ),
        FreshnessItem(
            label='Prometheus',
            status='Healthy' if has_prometheus_data else ('Info' if not selected_cluster_mode else 'Unavailable'),
            value=prometheus_value,
            icon='activity',
            description=prometheus_description,
        ),
        FreshnessItem(
            label='AlertManager',
            status='Healthy' if has_alertmanager_data else ('Info' if not selected_cluster_mode else 'Unavailable'),
            value=alertmanager_value,
            icon='bell-ring',
            description=alertmanager_description,
        ),
        FreshnessItem(
            label='Report Generation',
            status='Healthy' if reporting_snapshot.generated_reports > 0 else 'Unknown',
            value=f'{reporting_snapshot.generated_reports} generated'
            if reporting_snapshot.generated_reports
            else 'No reports yet',
            icon='file-text',
            description='Report freshness shows whether generated report artifacts already exist for operational review.',  # noqa: E501
        ),
    ]


def _capacity_percent(snapshot: CapacitySnapshot, label: str) -> float | None:
    for item in snapshot.items:
        if item.label.lower() == label.lower():
            return item.used_percent
    return None


def _percent_label(value: float | None) -> str:
    if value is None:
        return '—'
    return f'{value:.0f}%'


def _headroom(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, round(100.0 - value, 2))


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _risk_from_percent(value: float) -> str:
    if value >= 90:
        return 'Critical'
    if value >= 75:
        return 'High'
    if value >= 60:
        return 'Medium'
    return 'Low'


def _capacity_insight(risk: str, items: list[CapacityItem]) -> str:
    highest = max(items, key=lambda item: _safe_float(item.used_percent), default=None)
    if highest is None or highest.used_percent is None:
        return 'Capacity metrics are not available yet.'
    return f'{highest.label} is the highest utilization signal at {highest.used_percent:.0f}%. Overall risk: {risk}.'


def _forecast_insight(payload: dict[str, Any]) -> str:
    summary = payload.get('summary')
    if not isinstance(summary, dict):
        return 'Forecast snapshot loaded from analytics forecast service.'
    label = summary.get('highest_projected_label', 'resource')
    percent = summary.get('highest_projected_percent', 0)
    try:
        return f'{label} has the highest 30-day projection at {float(percent):.0f}%.'
    except (TypeError, ValueError):
        return 'Forecast snapshot loaded from analytics forecast service.'


def _kpi_metric_description(live_cluster: Any | None, fallback: str) -> str:
    if live_cluster is None:
        return 'Select a cluster for live metric'
    return fallback


def _format_gib(value: Any) -> str:
    number = _safe_float(value)
    gib = number / 1024**3
    if gib >= 1024:
        return f'{gib / 1024:.2f} TiB'
    return f'{gib:.2f} GiB'


def _latest_timestamp(items: Iterable[Any]) -> datetime | None:
    latest: datetime | None = None
    for item in items:
        value = _coerce_datetime(_get_attr(item, 'updated_at', 'collected_at', 'created_at', 'last_seen', 'last_sync'))
        if value is None:
            continue
        if latest is None or value > latest:
            latest = value
    return latest


def _coerce_datetime(value: Any) -> datetime | None:
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


def _human_time(value: datetime | None) -> str:
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
