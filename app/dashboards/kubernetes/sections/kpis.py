from __future__ import annotations

from app.dashboards.kubernetes.schema import DashboardKpi, DashboardKpiContext
from app.dashboards.kubernetes.utils import capacity_percent, count_cluster_status, percent_label


def build_kpis(context: DashboardKpiContext) -> list[DashboardKpi]:
    return [
        DashboardKpi(
            label='Clusters',
            value=str(len(context.clusters)),
            description=(
                f'{count_cluster_status(context.clusters_raw, "healthy")} Healthy • '
                f'{count_cluster_status(context.clusters_raw, "warning")} Warning'
            ),
            icon='network',
            tone='blue',
        ),
        DashboardKpi(
            label='Nodes',
            value=str(context.nodes_total),
            description=f'{context.nodes_ready} Ready • {context.not_ready_nodes} NotReady',
            icon='server',
            tone='emerald' if context.not_ready_nodes == 0 else 'amber',
        ),
        DashboardKpi(
            label='Namespaces',
            value=str(context.namespaces_total),
            description='Discovered Kubernetes Namespaces',
            icon='layout-grid',
            tone='violet',
        ),
        DashboardKpi(
            label='Workloads',
            value=str(context.workloads_total),
            description='Deployments, StatefulSets, DaemonSets, Jobs, CronJobs',
            icon='boxes',
            tone='blue',
        ),
        DashboardKpi(
            label='Pods',
            value=str(context.pods_total),
            description=f'{context.running_pods} Running • {context.unhealthy_pods} Need Attention',
            icon='container',
            tone='emerald' if context.unhealthy_pods == 0 else 'amber',
        ),
        DashboardKpi(
            label='CPU Usage',
            value=(
                percent_label(capacity_percent(context.capacity_snapshot, 'CPU'))
                if context.live_cluster is not None
                else 'N/A'
            ),
            description=(
                'Committed Worker Snapshot'
                if context.live_cluster is not None
                else 'Select a cluster to view committed CPU usage'
            ),
            icon='cpu',
            tone='orange' if context.live_cluster is not None else 'slate',
        ),
        DashboardKpi(
            label='Memory Usage',
            value=(
                percent_label(capacity_percent(context.capacity_snapshot, 'Memory'))
                if context.live_cluster is not None
                else 'N/A'
            ),
            description=(
                'Committed Worker Snapshot'
                if context.live_cluster is not None
                else 'Select a cluster to view committed memory usage'
            ),
            icon='memory-stick',
            tone='violet' if context.live_cluster is not None else 'slate',
        ),
        DashboardKpi(
            label='Active Alerts',
            value=context.active_alerts_label,
            description=context.active_alerts_description,
            icon='bell-ring',
            tone=(
                'red' if context.alerts_snapshot.critical else 'amber' if context.alerts_snapshot.warning else 'emerald'
            ),
        ),
    ]
