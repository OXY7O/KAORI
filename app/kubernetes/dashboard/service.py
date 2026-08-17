from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.kubernetes.analytics.materialization.keys import (
    CAPACITY_DATASET_KEY,
    DASHBOARD_ALERTS_DATASET_KEY,
    FORECAST_DATASET_KEY,
    TOP_CONSUMERS_DATASET_KEY,
)
from app.kubernetes.dashboard.repository import (
    count_records,
    count_records_with_values,
    latest_record_timestamp,
    query_all,
    query_for_clusters,
)
from app.kubernetes.dashboard.schema import (
    DashboardClusterOption,
    DashboardKpiContext,
    DashboardOverview,
    InventorySnapshot,
)
from app.kubernetes.dashboard.sections import (
    build_alerts_snapshot,
    build_capacity_snapshot,
    build_cluster_health,
    build_data_freshness,
    build_forecast_snapshot,
    build_kpis,
    build_recommendations,
    build_reporting_snapshot,
    build_top_consumers_snapshot,
    paginate_sequence,
)
from app.kubernetes.dashboard.snapshots import (
    alerts_parameters,
    capacity_parameters,
    forecast_parameters,
    read_dashboard_snapshot,
    top_consumers_parameters,
    unavailable_message,
)
from app.kubernetes.dashboard.utils import (
    coerce_datetime,
    get_attr,
    get_selected_cluster,
    human_time,
    normalize_selected_cluster,
)
from app.models import (
    Cluster,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)

_INVENTORY_MODELS = (
    NodeInventory,
    NamespaceInventory,
    WorkloadInventory,
    PodInventory,
    ServiceInventory,
    IngressInventory,
    StorageInventory,
)
_READY_NODE_STATES = {'ready', 'true', 'active', 'healthy'}
_RUNNING_POD_STATES = {'running'}
_UNHEALTHY_POD_STATES = {'pending', 'failed', 'unknown', 'crashloopbackoff', 'imagepullbackoff', 'error'}


def _scope(
    selected_cluster_id: str | None,
) -> tuple[list[Any], list[DashboardClusterOption], str | None, Any | None]:
    clusters_raw = query_all(Cluster)
    clusters = [
        DashboardClusterOption(
            id=str(get_attr(cluster, 'id', default='')),
            name=str(get_attr(cluster, 'name', default='Unnamed Cluster')),
        )
        for cluster in clusters_raw
    ]
    normalized = normalize_selected_cluster(selected_cluster_id, clusters)
    selected = get_selected_cluster(clusters_raw=clusters_raw, selected_cluster_id=normalized)
    return clusters_raw, clusters, normalized, selected


def _base_dashboard(
    *,
    clusters: list[DashboardClusterOption],
    selected_cluster_id: str | None,
    active_tab: str = 'overview',
) -> DashboardOverview:
    return DashboardOverview(
        clusters=clusters,
        selected_cluster_id=selected_cluster_id,
        active_tab=active_tab,
        meta={'generated_at': datetime.now(UTC).isoformat()},
    )


def _capacity_signal(cluster: Any):
    cluster_id = str(cluster.id)
    result = read_dashboard_snapshot(
        cluster_id=cluster_id,
        dataset_key=CAPACITY_DATASET_KEY,
        parameters=capacity_parameters(cluster_id),
    )
    return build_capacity_snapshot(
        context=result.context,
        unavailable_reason=unavailable_message('Capacity', result),
    ), result


def _alerts_signal(cluster: Any):
    cluster_id = str(cluster.id)
    result = read_dashboard_snapshot(
        cluster_id=cluster_id,
        dataset_key=DASHBOARD_ALERTS_DATASET_KEY,
        parameters=alerts_parameters(cluster_id),
    )
    return build_alerts_snapshot(
        context=result.context,
        unavailable_reason=unavailable_message('Alerts', result),
    ), result


def _top_consumers_signal(cluster: Any):
    cluster_id = str(cluster.id)
    result = read_dashboard_snapshot(
        cluster_id=cluster_id,
        dataset_key=TOP_CONSUMERS_DATASET_KEY,
        parameters=top_consumers_parameters(cluster_id),
    )
    return build_top_consumers_snapshot(
        context=result.context,
        unavailable_reason=unavailable_message('Top consumers', result),
    ), result


def _forecast_signal(cluster: Any):
    cluster_id = str(cluster.id)
    result = read_dashboard_snapshot(
        cluster_id=cluster_id,
        dataset_key=FORECAST_DATASET_KEY,
        parameters=forecast_parameters(cluster_id),
    )
    return build_forecast_snapshot(
        context=result.context,
        unavailable_reason=unavailable_message('Forecast', result),
    ), result


def _inventory_snapshot(selected_cluster_id: str | None) -> InventorySnapshot:
    return InventorySnapshot(
        namespaces=count_records(NamespaceInventory, selected_cluster_id),
        workloads=count_records(WorkloadInventory, selected_cluster_id),
        pods=count_records(PodInventory, selected_cluster_id),
        services=count_records(ServiceInventory, selected_cluster_id),
        ingresses=count_records(IngressInventory, selected_cluster_id),
        storage=count_records(StorageInventory, selected_cluster_id),
        running_pods=count_records_with_values(
            PodInventory,
            'phase',
            _RUNNING_POD_STATES,
            selected_cluster_id,
        ),
        unhealthy_pods=count_records_with_values(
            PodInventory,
            'phase',
            _UNHEALTHY_POD_STATES,
            selected_cluster_id,
        ),
    )


def _latest_inventory_sync(selected_cluster_id: str | None):
    timestamps = [coerce_datetime(latest_record_timestamp(model, selected_cluster_id)) for model in _INVENTORY_MODELS]
    return max((value for value in timestamps if value is not None), default=None)


def _group_by_cluster(rows: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        cluster_id = str(get_attr(row, 'cluster_id', default=''))
        grouped.setdefault(cluster_id, []).append(row)
    return grouped


def get_dashboard_overview(
    selected_cluster_id: str | None = None,
    cluster_health_page: str | int | None = 1,
    cluster_health_per_page: int = 5,
    active_tab: str = 'overview',
) -> DashboardOverview:
    """Build the database-only dashboard shell; live integrations are never called here."""
    _clusters_raw, clusters, selected_cluster_id, _selected = _scope(selected_cluster_id)
    dashboard = _base_dashboard(
        clusters=clusters,
        selected_cluster_id=selected_cluster_id,
        active_tab=active_tab,
    )
    dashboard.inventory_snapshot = _inventory_snapshot(selected_cluster_id)
    dashboard.reporting_snapshot = build_reporting_snapshot(selected_cluster_id=selected_cluster_id)
    latest_sync = _latest_inventory_sync(selected_cluster_id)
    dashboard.last_updated = human_time(latest_sync) if latest_sync else 'No sync yet'
    _cluster_health_rows, pagination = paginate_sequence(
        items=clusters,
        page=cluster_health_page,
        per_page=cluster_health_per_page,
    )
    dashboard.cluster_health_pagination = pagination
    return dashboard


def get_dashboard_section(
    section: str,
    *,
    selected_cluster_id: str | None = None,
    cluster_health_page: str | int | None = 1,
    cluster_health_per_page: int = 5,
) -> DashboardOverview:
    """Build one section from inventory tables and committed worker snapshots only."""
    clusters_raw, clusters, selected_cluster_id, selected = _scope(selected_cluster_id)
    dashboard = _base_dashboard(clusters=clusters, selected_cluster_id=selected_cluster_id)

    if section == 'cluster_health':
        scoped_clusters = clusters_raw
        if selected_cluster_id:
            scoped_clusters = [cluster for cluster in clusters_raw if str(cluster.id) == selected_cluster_id]
        visible, pagination = paginate_sequence(
            items=scoped_clusters,
            page=cluster_health_page,
            per_page=cluster_health_per_page,
        )
        visible_cluster_ids = [str(cluster.id) for cluster in visible]
        node_rows = query_for_clusters(NodeInventory, visible_cluster_ids)
        pod_rows = query_for_clusters(PodInventory, visible_cluster_ids)
        capacities = {}
        alerts = {}
        for cluster in visible:
            capacity, _ = _capacity_signal(cluster)
            alert_snapshot, _ = _alerts_signal(cluster)
            capacities[str(cluster.id)] = capacity
            alerts[str(cluster.id)] = alert_snapshot
        dashboard.cluster_health_snapshot = build_cluster_health(
            clusters_raw=visible,
            selected_cluster_id=None,
            nodes_by_cluster=_group_by_cluster(node_rows),
            pods_by_cluster=_group_by_cluster(pod_rows),
            capacity_by_cluster=capacities,
            alerts_by_cluster=alerts,
        )
        dashboard.cluster_health_pagination = pagination
        return dashboard

    if section == 'recommended_actions':
        dashboard.recommended_actions = build_recommendations(selected_cluster_id=selected_cluster_id)
        return dashboard

    if section == 'kpi_cards':
        if selected is not None:
            dashboard.capacity_snapshot, _ = _capacity_signal(selected)
            dashboard.alerts_snapshot, _ = _alerts_signal(selected)
        inventory = _inventory_snapshot(selected_cluster_id)
        nodes_total = count_records(NodeInventory, selected_cluster_id)
        nodes_ready = count_records_with_values(
            NodeInventory,
            'status',
            _READY_NODE_STATES,
            selected_cluster_id,
        )
        active_alerts = (
            dashboard.alerts_snapshot.critical + dashboard.alerts_snapshot.warning + dashboard.alerts_snapshot.info
        )
        dashboard.global_kpis = build_kpis(
            DashboardKpiContext(
                clusters_raw=clusters_raw,
                clusters=clusters,
                nodes_total=nodes_total,
                nodes_ready=nodes_ready,
                not_ready_nodes=max(nodes_total - nodes_ready, 0),
                namespaces_total=inventory.namespaces,
                workloads_total=inventory.workloads,
                pods_total=inventory.pods,
                running_pods=inventory.running_pods,
                unhealthy_pods=inventory.unhealthy_pods,
                capacity_snapshot=dashboard.capacity_snapshot,
                alerts_snapshot=dashboard.alerts_snapshot,
                selected_cluster=selected,
                active_alerts_label=str(active_alerts) if selected is not None else 'N/A',
                active_alerts_description=(
                    f'{dashboard.alerts_snapshot.critical} Critical • {dashboard.alerts_snapshot.warning} Warning'
                    if selected is not None
                    else 'Select a cluster to view committed alert signals'
                ),
            )
        )
        return dashboard

    if section == 'capacity_snapshot':
        if selected is not None:
            dashboard.capacity_snapshot, _ = _capacity_signal(selected)
        return dashboard

    if section == 'alerts_summary':
        if selected is not None:
            dashboard.alerts_snapshot, _ = _alerts_signal(selected)
        return dashboard

    if section == 'top_consumers':
        if selected is not None:
            dashboard.top_consumers_snapshot, _ = _top_consumers_signal(selected)
        return dashboard

    if section == 'forecast_risk':
        if selected is not None:
            dashboard.forecast_snapshot, _ = _forecast_signal(selected)
        return dashboard

    if section == 'data_freshness':
        capacity_result = alerts_result = top_result = forecast_result = None
        if selected is not None:
            dashboard.capacity_snapshot, capacity_result = _capacity_signal(selected)
            dashboard.alerts_snapshot, alerts_result = _alerts_signal(selected)
            dashboard.top_consumers_snapshot, top_result = _top_consumers_signal(selected)
            dashboard.forecast_snapshot, forecast_result = _forecast_signal(selected)
        latest_sync = _latest_inventory_sync(selected_cluster_id)
        dashboard.reporting_snapshot = build_reporting_snapshot(selected_cluster_id=selected_cluster_id)
        has_metrics_source_data = any(
            snapshot.source_status == 'Available'
            for snapshot in (
                dashboard.capacity_snapshot,
                dashboard.top_consumers_snapshot,
                dashboard.forecast_snapshot,
            )
        )
        dashboard.data_freshness = build_data_freshness(
            latest_inventory_sync=latest_sync,
            has_metrics_source_data=has_metrics_source_data,
            has_alertmanager_data=dashboard.alerts_snapshot.source_status == 'Available',
            reporting_snapshot=dashboard.reporting_snapshot,
            selected_cluster=selected,
        )
        dashboard.meta['snapshot_states'] = {
            'capacity': getattr(capacity_result, 'state', 'not_applicable'),
            'alerts': getattr(alerts_result, 'state', 'not_applicable'),
            'top_consumers': getattr(top_result, 'state', 'not_applicable'),
            'forecast': getattr(forecast_result, 'state', 'not_applicable'),
        }
        return dashboard

    return dashboard
