from __future__ import annotations

from types import SimpleNamespace

from app.common.pagination import paginate_sequence
from app.kubernetes.dashboard.schema import DashboardClusterOption, ReportingSnapshot
from app.kubernetes.dashboard.sections.freshness import build_data_freshness
from app.kubernetes.dashboard.sections.top_consumers import build_top_consumers_snapshot
from app.kubernetes.dashboard.utils import get_selected_cluster, normalize_selected_cluster


def test_dashboard_pagination_is_bounded_and_clamps_invalid_pages() -> None:
    items = list(range(12))

    visible, pagination = paginate_sequence(items=items, page='99', per_page=5)

    assert visible == [10, 11]
    assert pagination['page'] == 3
    assert pagination['total_pages'] == 3
    assert pagination['start_item'] == 11
    assert pagination['end_item'] == 12
    assert pagination['allowed_per_page'] == [5, 10, 25, 50]


def test_dashboard_selected_cluster_resolution_accepts_only_catalog_ids() -> None:
    clusters = [DashboardClusterOption(id='a', name='A'), DashboardClusterOption(id='b', name='B')]
    raw = [SimpleNamespace(id='a'), SimpleNamespace(id='b')]

    assert normalize_selected_cluster('b', clusters) == 'b'
    assert normalize_selected_cluster('unknown', clusters) is None
    assert get_selected_cluster(clusters_raw=raw, selected_cluster_id='b') is raw[1]
    assert get_selected_cluster(clusters_raw=raw, selected_cluster_id=None) is None


def test_empty_top_consumer_insight_describes_committed_snapshot_not_live_provider_query() -> None:
    snapshot = build_top_consumers_snapshot(
        context={'consumer_payload': {'rows': []}},
        unavailable_reason='Unavailable.',
    )

    assert 'committed top consumer snapshot' in snapshot.insight_description.lower()
    assert 'committed worker snapshot' in snapshot.insight_items[0].lower()
    assert 'returned by prometheus' not in snapshot.insight_description.lower()


def test_kubernetes_fleet_freshness_uses_committed_coverage_not_scope_hint() -> None:
    cases = [
        (0, 0, 'Required', 'Required', '0 / 0 clusters'),
        (0, 3, 'Required', 'Required', '0 / 3 clusters'),
        (1, 3, 'Partial', 'Partial', '1 / 3 clusters'),
        (3, 3, 'Ready', 'Ready', '3 / 3 clusters'),
    ]
    for ready, total, expected_metrics, expected_alerts, value in cases:
        rows = build_data_freshness(
            latest_inventory_sync=None,
            has_metrics_source_data=False,
            has_alertmanager_data=False,
            reporting_snapshot=ReportingSnapshot(),
            selected_cluster=None,
            fleet_cluster_count=total,
            fleet_metrics_count=ready,
            fleet_alerts_count=ready,
        )
        assert len(rows) == 4
        assert [row.label for row in rows] == [
            'Inventory Snapshot', 'Metrics Snapshot', 'Alert Snapshot', 'Report Artifacts'
        ]
        assert rows[1].status == expected_metrics
        assert rows[2].status == expected_alerts
        assert rows[1].value == value
        assert rows[2].value == value
        assert rows[1].tone == rows[2].tone
        assert 'Select a cluster' in rows[1].description
        assert 'Select a cluster' in rows[2].description

    mixed = build_data_freshness(
        latest_inventory_sync=None,
        has_metrics_source_data=False,
        has_alertmanager_data=False,
        reporting_snapshot=ReportingSnapshot(),
        selected_cluster=None,
        fleet_cluster_count=3,
        fleet_metrics_count=3,
        fleet_alerts_count=1,
    )
    assert mixed[1].status == 'Ready'
    assert mixed[2].status == 'Partial'
