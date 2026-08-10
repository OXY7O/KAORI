from __future__ import annotations

from datetime import datetime
from typing import Any

from app.dashboards.kubernetes.schema import FreshnessItem, ReportingSnapshot
from app.dashboards.kubernetes.utils import human_time


def build_data_freshness(
    *,
    latest_inventory_sync: datetime | None,
    has_prometheus_data: bool,
    has_alertmanager_data: bool,
    reporting_snapshot: ReportingSnapshot,
    selected_cluster: Any | None,
) -> list[FreshnessItem]:
    selected_cluster_mode = selected_cluster is not None

    if selected_cluster_mode:
        prometheus_status = 'Ready' if has_prometheus_data else 'Unavailable'
        prometheus_tone = 'normal' if has_prometheus_data else 'unknown'
        prometheus_value = (
            'Committed analytics snapshot available' if has_prometheus_data else 'No committed analytics snapshot'
        )
        prometheus_description = (
            'Prometheus-backed utilization, capacity, consumer, and forecast data for the selected cluster.'
            if has_prometheus_data
            else (
                'Run or validate analytics materialization for the selected cluster before using '
                'detailed metric signals.'
            )
        )

        alert_status = 'Ready' if has_alertmanager_data else 'Unavailable'
        alert_tone = 'normal' if has_alertmanager_data else 'unknown'
        alert_value = 'Committed alert snapshot available' if has_alertmanager_data else 'No committed alert snapshot'
        alert_description = (
            'Alertmanager or Prometheus alert data is available for the selected cluster.'
            if has_alertmanager_data
            else 'Validate the alert source and refresh the selected cluster before relying on alert signals.'
        )
    else:
        prometheus_status = 'Per Cluster'
        prometheus_tone = 'info'
        prometheus_value = 'Resolved from committed cluster snapshots'
        prometheus_description = (
            'All Clusters mode summarizes committed capacity snapshots by cluster. '
            'Select one cluster for detailed analytics.'
        )

        alert_status = 'Per Cluster'
        alert_tone = 'info'
        alert_value = 'Resolved from committed cluster snapshots'
        alert_description = (
            'All Clusters mode summarizes committed alert snapshots by cluster. Select one cluster for source details.'
        )

    has_reports = reporting_snapshot.generated_reports > 0

    return [
        FreshnessItem(
            label='Inventory Snapshot',
            status='Current' if latest_inventory_sync else 'Not Synced',
            tone='normal' if latest_inventory_sync else 'unknown',
            value=(
                f'Updated {human_time(latest_inventory_sync)}'
                if latest_inventory_sync
                else 'No committed inventory snapshot'
            ),
            icon='database-zap',
            description=(
                'Latest synchronized Kubernetes object counts used by the dashboard and Inventory workspaces.'
            ),
        ),
        FreshnessItem(
            label='Metrics Snapshot',
            status=prometheus_status,
            tone=prometheus_tone,
            value=prometheus_value,
            icon='activity',
            description=prometheus_description,
        ),
        FreshnessItem(
            label='Alert Snapshot',
            status=alert_status,
            tone=alert_tone,
            value=alert_value,
            icon='bell-ring',
            description=alert_description,
        ),
        FreshnessItem(
            label='Report Artifacts',
            status='Available' if has_reports else 'Not Generated',
            tone='normal' if has_reports else 'unknown',
            value=(
                f'{reporting_snapshot.generated_reports} generated reports'
                if has_reports
                else 'No generated report artifacts'
            ),
            icon='file-text',
            description=(
                'Generated reports are retained operational artifacts, separate from current Kubernetes health signals.'
            ),
        ),
    ]
