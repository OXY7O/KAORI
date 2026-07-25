from __future__ import annotations

from datetime import datetime
from typing import Any

from app.dashboards.kubernetes.schema import AlertsSnapshot, CapacitySnapshot, FreshnessItem, ReportingSnapshot
from app.dashboards.kubernetes.utils import human_time


def build_hero_integration_meta(
    *,
    live_cluster: Any | None,
    capacity_snapshot: CapacitySnapshot,
    alerts_snapshot: AlertsSnapshot,
) -> dict[str, str]:
    if live_cluster is None:
        return {
            'prometheus_status_label': 'Per-cluster',
            'prometheus_status_description': 'Committed snapshots shown by cluster',
            'prometheus_status_tone': 'blue',
            'alertmanager_status_label': 'Per-cluster',
            'alertmanager_status_description': 'Committed snapshots shown by cluster',
            'alertmanager_status_tone': 'blue',
        }

    prometheus_available = capacity_snapshot.source_status == 'Available'
    alertmanager_available = alerts_snapshot.source_status == 'Available'

    return {
        'prometheus_status_label': 'Snapshot Ready' if prometheus_available else 'Unavailable',
        'prometheus_status_description': 'Worker snapshot available' if prometheus_available else 'Awaiting worker refresh',
        'prometheus_status_tone': 'green' if prometheus_available else 'slate',
        'alertmanager_status_label': 'Snapshot Ready' if alertmanager_available else 'Unavailable',
        'alertmanager_status_description': (
            'Worker snapshot available' if alertmanager_available else 'Awaiting worker refresh'
        ),
        'alertmanager_status_tone': 'green' if alertmanager_available else 'slate',
    }


def build_data_freshness(
    *,
    latest_inventory_sync: datetime | None,
    has_prometheus_data: bool,
    has_alertmanager_data: bool,
    reporting_snapshot: ReportingSnapshot,
    live_cluster: Any | None,
) -> list[FreshnessItem]:
    selected_cluster_mode = live_cluster is not None

    prometheus_value = 'Snapshot Ready' if has_prometheus_data else 'Unavailable'
    prometheus_description = (
        'Committed Prometheus-backed analytics snapshots are available for the selected cluster.'
    )
    if not selected_cluster_mode:
        prometheus_value = 'Per-cluster snapshots'
        prometheus_description = (
            'All Clusters mode reads committed capacity snapshots for each visible Cluster Health row. '
            'Select one cluster to inspect detailed capacity, top consumer, and forecast snapshots.'
        )
    elif not has_prometheus_data:
        prometheus_description = (
            'No committed Prometheus-backed analytics snapshot is currently available for the selected cluster.'
        )

    alertmanager_value = 'Snapshot Ready' if has_alertmanager_data else 'Unavailable'
    alertmanager_description = (
        'A committed AlertManager or Prometheus alert snapshot is available for the selected cluster.'
    )
    if not selected_cluster_mode:
        alertmanager_value = 'Per-cluster snapshots'
        alertmanager_description = (
            'All Clusters mode reads committed alert snapshots for each visible Cluster Health row. '
            'Select one cluster to inspect alert details and source context.'
        )
    elif not has_alertmanager_data:
        alertmanager_description = 'No committed alert snapshot is currently available for the selected cluster.'

    return [
        FreshnessItem(
            label='Inventory Sync',
            status='Healthy' if latest_inventory_sync else 'Unknown',
            value=human_time(latest_inventory_sync) if latest_inventory_sync else 'No sync yet',
            icon='refresh-cw',
            description=(
                'Database inventory and report summaries use the latest collected snapshot for the selected dashboard scope.'
            ),
        ),
        FreshnessItem(
            label='Prometheus Analytics',
            status='Healthy' if has_prometheus_data else ('Info' if not selected_cluster_mode else 'Unavailable'),
            value=prometheus_value,
            icon='activity',
            description=prometheus_description,
        ),
        FreshnessItem(
            label='Alert Signals',
            status='Healthy' if has_alertmanager_data else ('Info' if not selected_cluster_mode else 'Unavailable'),
            value=alertmanager_value,
            icon='bell-ring',
            description=alertmanager_description,
        ),
        FreshnessItem(
            label='Report Generation',
            status='Healthy' if reporting_snapshot.generated_reports > 0 else 'Unknown',
            value=(
                f'{reporting_snapshot.generated_reports} generated'
                if reporting_snapshot.generated_reports
                else 'No reports yet'
            ),
            icon='file-text',
            description='Report freshness shows whether generated report artifacts exist for operational review.',
        ),
    ]
