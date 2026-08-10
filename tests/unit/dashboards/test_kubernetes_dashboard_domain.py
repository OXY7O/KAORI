from __future__ import annotations

from types import SimpleNamespace

from app.dashboards.kubernetes.schema import DashboardClusterOption
from app.dashboards.kubernetes.sections.cluster_health import paginate_sequence
from app.dashboards.kubernetes.sections.top_consumers import build_top_consumers_snapshot
from app.dashboards.kubernetes.utils import get_selected_cluster, normalize_selected_cluster


def test_dashboard_pagination_is_bounded_and_clamps_invalid_pages() -> None:
    items = list(range(12))

    visible, pagination = paginate_sequence(items=items, page='99', per_page=5)

    assert visible == [10, 11]
    assert pagination.page == 3
    assert pagination.total_pages == 3
    assert pagination.start_item == 11
    assert pagination.end_item == 12


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
