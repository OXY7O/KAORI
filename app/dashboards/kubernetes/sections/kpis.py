from __future__ import annotations

from app.dashboards.kubernetes.schema import (
    AlertsSnapshot,
    CapacitySnapshot,
    DashboardClusterOption,
    DashboardKpi,
)
from app.dashboards.kubernetes.utils import (
    capacity_percent,
    count_cluster_status,
    kpi_metric_description,
    percent_label,
)


def build_kpis(
    *,
    clusters_raw: list[object],
    clusters: list[DashboardClusterOption],
    nodes_total: int,
    nodes_ready: int,
    not_ready_nodes: int,
    namespaces_total: int,
    workloads_total: int,
    pods_total: int,
    running_pods: int,
    unhealthy_pods: int,
    capacity_snapshot: CapacitySnapshot,
    alerts_snapshot: AlertsSnapshot,
    live_cluster: object | None,
    active_alerts_label: str,
    active_alerts_description: str,
) -> list[DashboardKpi]:
    return [
        DashboardKpi(
            label='Clusters',
            value=str(len(clusters)),
            description=(
                f'{count_cluster_status(clusters_raw, "healthy")} healthy • '
                f'{count_cluster_status(clusters_raw, "warning")} warning'
            ),
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
            value=str(namespaces_total),
            description='Discovered Kubernetes namespaces',
            icon='layout-grid',
            tone='violet',
        ),
        DashboardKpi(
            label='Workloads',
            value=str(workloads_total),
            description='Deployments, StatefulSets, DaemonSets, Jobs, CronJobs',
            icon='boxes',
            tone='blue',
        ),
        DashboardKpi(
            label='Pods',
            value=str(pods_total),
            description=f'{running_pods} Running • {unhealthy_pods} need attention',
            icon='container',
            tone='emerald' if unhealthy_pods == 0 else 'amber',
        ),
        DashboardKpi(
            label='CPU Usage',
            value=percent_label(capacity_percent(capacity_snapshot, 'CPU')) if live_cluster is not None else 'N/A',
            description=(
                kpi_metric_description(live_cluster, 'Current usage snapshot')
                if live_cluster is not None
                else 'Select a cluster to view live Prometheus CPU usage'
            ),
            icon='cpu',
            tone='orange' if live_cluster is not None else 'slate',
        ),
        DashboardKpi(
            label='Memory Usage',
            value=percent_label(capacity_percent(capacity_snapshot, 'Memory')) if live_cluster is not None else 'N/A',
            description=(
                kpi_metric_description(live_cluster, 'Current usage snapshot')
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
