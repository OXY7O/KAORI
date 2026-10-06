from __future__ import annotations

from datetime import UTC, datetime

from app.kubernetes.dashboard.schema import ReportingSnapshot
from app.kubernetes.dashboard.sections.freshness import build_data_freshness


def test_selected_cluster_freshness_uses_specific_status_labels() -> None:
    items = build_data_freshness(
        latest_inventory_sync=datetime.now(UTC),
        has_metrics_source_data=True,
        has_alertmanager_data=False,
        reporting_snapshot=ReportingSnapshot(generated_reports=3),
        selected_cluster=object(),
    )

    assert [item.label for item in items] == [
        'Inventory Snapshot',
        'Metrics Snapshot',
        'Alert Snapshot',
        'Report Artifacts',
    ]
    assert [item.status for item in items] == [
        'Current',
        'Ready',
        'Unavailable',
        'Available',
    ]
    assert [item.tone for item in items] == [
        'normal',
        'normal',
        'unknown',
        'normal',
    ]


def test_fleet_freshness_distinguishes_scope_from_missing_data() -> None:
    items = build_data_freshness(
        latest_inventory_sync=None,
        has_metrics_source_data=False,
        has_alertmanager_data=False,
        reporting_snapshot=ReportingSnapshot(),
        selected_cluster=None,
    )

    assert [item.status for item in items] == [
        'Not Synced',
        'Per Cluster',
        'Per Cluster',
        'Not Generated',
    ]
    assert [item.tone for item in items] == [
        'unknown',
        'info',
        'info',
        'unknown',
    ]
