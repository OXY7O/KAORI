from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from app.dashboards.kubernetes.repository import load_models, query_all
from app.dashboards.kubernetes.schema import (
    DashboardClusterOption,
    DashboardOverview,
    ForecastSnapshot,
    InventorySnapshot,
)
from app.dashboards.kubernetes.sections import (
    alerts_snapshot_with_message,
    build_alerts_snapshot,
    build_capacity_snapshot,
    build_cluster_health,
    build_data_freshness,
    build_forecast_snapshot,
    build_hero_integration_meta,
    build_kpis,
    build_recommendations,
    build_reporting_snapshot,
    build_top_consumers_snapshot,
    default_forecast_items,
    empty_capacity_snapshot,
    paginate_sequence,
    top_consumers_snapshot_with_message,
)
from app.dashboards.kubernetes.utils import (
    get_attr,
    get_live_cluster,
    human_time,
    is_ready_node,
    is_unhealthy_pod,
    latest_timestamp,
    normalize_selected_cluster,
    normalize_status,
)


def get_dashboard_overview(
    selected_cluster_id: str | None = None,
    cluster_health_page: str | int | None = 1,
    *,
    hydrate_live_sections: bool = True,
    live_sections: Iterable[str] | None = None,
) -> DashboardOverview:
    models = load_models()

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

    clusters_raw = query_all(Cluster) if Cluster else []
    clusters = [
        DashboardClusterOption(
            id=str(get_attr(cluster, 'id', default='')),
            name=str(get_attr(cluster, 'name', default='Unnamed Cluster')),
        )
        for cluster in clusters_raw
    ]

    selected_cluster_id = normalize_selected_cluster(selected_cluster_id, clusters)
    live_cluster = get_live_cluster(clusters_raw=clusters_raw, selected_cluster_id=selected_cluster_id)

    nodes = query_all(NodeInventory, selected_cluster_id) if NodeInventory else []
    namespaces = query_all(NamespaceInventory, selected_cluster_id) if NamespaceInventory else []
    workloads = query_all(WorkloadInventory, selected_cluster_id) if WorkloadInventory else []
    pods = query_all(PodInventory, selected_cluster_id) if PodInventory else []
    services = query_all(ServiceInventory, selected_cluster_id) if ServiceInventory else []
    ingresses = query_all(IngressInventory, selected_cluster_id) if IngressInventory else []
    storage_items = query_all(StorageInventory, selected_cluster_id) if StorageInventory else []

    capacity_snapshot = (
        build_capacity_snapshot(live_cluster=live_cluster, selected_cluster_id=selected_cluster_id)
        if should_hydrate('capacity', 'capacity_snapshot', 'kpi_cards', 'data_freshness', 'recommended_actions', 'hero')
        else empty_capacity_snapshot(insight='Live capacity snapshot will load after the dashboard shell is ready.')
    )
    alerts_snapshot = (
        build_alerts_snapshot(live_cluster=live_cluster)
        if should_hydrate('alerts', 'alerts_summary', 'kpi_cards', 'data_freshness', 'recommended_actions', 'hero')
        else alerts_snapshot_with_message('Live alert snapshot will load after the dashboard shell is ready.')
    )
    top_consumers_snapshot = (
        build_top_consumers_snapshot(live_cluster=live_cluster)
        if should_hydrate('top_consumers', 'data_freshness')
        else top_consumers_snapshot_with_message('Top consumer snapshot will load after the dashboard shell is ready.')
    )
    forecast_snapshot = (
        build_forecast_snapshot(live_cluster=live_cluster)
        if should_hydrate('forecast', 'forecast_risk', 'data_freshness')
        else ForecastSnapshot(
            items=default_forecast_items('Pending', 'Waiting for trend snapshot'),
            insight='Forecast snapshot will load after the dashboard shell is ready.',
            source_status='Unavailable',
        )
    )
    reporting_snapshot = build_reporting_snapshot(selected_cluster_id=selected_cluster_id)

    nodes_total = len(nodes)
    nodes_ready = sum(1 for node in nodes if is_ready_node(node))
    not_ready_nodes = max(nodes_total - nodes_ready, 0)
    running_pods = sum(
        1 for pod in pods if normalize_status(get_attr(pod, 'status', 'phase', default='')) == 'running'
    )
    unhealthy_pods = sum(1 for pod in pods if is_unhealthy_pod(pod))

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
            cluster for cluster in clusters_raw if str(get_attr(cluster, 'id', default='')) == selected_cluster_id
        ]

    health_clusters_page, cluster_health_pagination = paginate_sequence(
        items=clusters_for_health,
        page=cluster_health_page,
        per_page=5,
    )
    cluster_health = build_cluster_health(
        clusters_raw=health_clusters_page,
        selected_cluster_id=None,
        NodeInventory=NodeInventory,
        PodInventory=PodInventory,
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

    kpis = build_kpis(
        clusters_raw=clusters_raw,
        clusters=clusters,
        nodes_total=nodes_total,
        nodes_ready=nodes_ready,
        not_ready_nodes=not_ready_nodes,
        namespaces_total=len(namespaces),
        workloads_total=len(workloads),
        pods_total=len(pods),
        running_pods=running_pods,
        unhealthy_pods=unhealthy_pods,
        capacity_snapshot=capacity_snapshot,
        alerts_snapshot=alerts_snapshot,
        live_cluster=live_cluster,
        active_alerts_label=active_alerts_label,
        active_alerts_description=active_alerts_description,
    )

    latest_sync = latest_timestamp([*nodes, *pods, *workloads, *namespaces, *services, *ingresses, *storage_items])
    last_updated = human_time(latest_sync) if latest_sync else 'Just now'

    data_freshness = build_data_freshness(
        latest_inventory_sync=latest_sync,
        has_prometheus_data=has_prometheus_data,
        has_alertmanager_data=has_alertmanager_data,
        reporting_snapshot=reporting_snapshot,
        live_cluster=live_cluster,
    )
    recommendations = (
        build_recommendations(selected_cluster_id=selected_cluster_id)
        if should_hydrate('recommended_actions')
        else []
    )
    hero_integration_meta = build_hero_integration_meta(
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
