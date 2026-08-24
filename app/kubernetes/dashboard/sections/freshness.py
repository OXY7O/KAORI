from __future__ import annotations

from datetime import datetime
from typing import Any

from app.kubernetes.dashboard.schema import FreshnessItem, ReportingSnapshot
from app.kubernetes.dashboard.utils import human_time


def build_data_freshness(
    *,
    latest_inventory_sync: datetime | None,
    has_metrics_source_data: bool,
    has_alertmanager_data: bool,
    reporting_snapshot: ReportingSnapshot,
    selected_cluster: Any | None,
) -> list[FreshnessItem]:
    selected_cluster_mode = selected_cluster is not None

    if selected_cluster_mode:
        metrics_source_status = 'Ready' if has_metrics_source_data else 'Unavailable'
        metrics_source_tone = 'normal' if has_metrics_source_data else 'unknown'
        metrics_source_value = (
            'Committed analytics available' if has_metrics_source_data else 'No committed analytics snapshot'
        )
        metrics_source_description = (
            'Metrics Source-backed utilization, capacity, consumer, and forecast data for the selected cluster.'
            if has_metrics_source_data
            else (
                'Run or validate analytics materialization for the selected cluster before using '
                'detailed metric signals.'
            )
        )

        alert_status = 'Ready' if has_alertmanager_data else 'Unavailable'
        alert_tone = 'normal' if has_alertmanager_data else 'unknown'
        alert_value = 'Committed alert snapshot available' if has_alertmanager_data else 'No committed alert snapshot'
        alert_description = (
            'Alertmanager or Metrics Source alert data is available for the selected cluster.'
            if has_alertmanager_data
            else 'Validate the alert source and refresh the selected cluster before relying on alert signals.'
        )
    else:
        metrics_source_status = 'Per Cluster'
        metrics_source_tone = 'info'
        metrics_source_value = 'Resolved from committed cluster snapshots'
        metrics_source_description = (
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
            status=metrics_source_status,
            tone=metrics_source_tone,
            value=metrics_source_value,
            icon='activity',
            description=metrics_source_description,
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
            description=('Generated reports are retained artifacts, separate from current Kubernetes health.'),
        ),
    ]
