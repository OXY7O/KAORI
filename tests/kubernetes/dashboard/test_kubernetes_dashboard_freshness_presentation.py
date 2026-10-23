from __future__ import annotations

from datetime import UTC, datetime

from app.kubernetes.dashboard.schema import ReportingSnapshot
from app.kubernetes.dashboard.sections.freshness import build_data_freshness


def test_selected_cluster_freshness_uses_specific_status_labels() -> None:
    items = build_data_freshness(
        latest_inventory_sync=datetime.now(UTC),
        has_metrics_source_data=True,
        has_alertmanager_data=False,
        reporting_snapshot=ReportingSnapshot(generated_reports=3, artifact_records=1),
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
        'Recorded',
    ]
    assert [item.tone for item in items] == [
        'normal',
        'normal',
        'unknown',
        'info',
    ]


def test_fleet_freshness_requires_committed_coverage_when_missing() -> None:
    items = build_data_freshness(
        latest_inventory_sync=None,
        has_metrics_source_data=False,
        has_alertmanager_data=False,
        reporting_snapshot=ReportingSnapshot(),
        selected_cluster=None,
        fleet_cluster_count=4,
        fleet_metrics_count=0,
        fleet_alerts_count=0,
    )

    assert [item.status for item in items] == [
        'Not Synced',
        'Required',
        'Required',
        'Not Generated',
    ]
    assert [item.tone for item in items] == [
        'unknown',
        'unknown',
        'unknown',
        'unknown',
    ]
    assert [item.value for item in items[1:3]] == ['0 / 4 clusters', '0 / 4 clusters']


def test_report_artifacts_do_not_claim_availability_from_pending_or_failed_records() -> None:
    for total, expected_status, expected_value in (
        (0, 'Not Generated', 'No report records'),
        (3, 'Not Ready', 'No ready artifact records'),
    ):
        items = build_data_freshness(
            latest_inventory_sync=None,
            has_metrics_source_data=False,
            has_alertmanager_data=False,
            reporting_snapshot=ReportingSnapshot(generated_reports=total, artifact_records=0),
            selected_cluster=object(),
        )
        report = next(item for item in items if item.label == 'Report Artifacts')
        assert report.status == expected_status
        assert report.value == expected_value
        assert report.tone != 'normal'
        assert 'storage accessibility is not verified' in report.description


def test_retained_reference_is_not_claimed_as_verified_storage_access() -> None:
    items = build_data_freshness(
        latest_inventory_sync=None,
        has_metrics_source_data=False,
        has_alertmanager_data=False,
        reporting_snapshot=ReportingSnapshot(generated_reports=3, artifact_records=2),
        selected_cluster=None,
    )
    report = next(item for item in items if item.label == 'Report Artifacts')
    assert report.status == 'Recorded'
    assert report.tone == 'info'
    assert report.value == '2 retained artifact records'
    assert 'storage accessibility is not verified' in report.description
