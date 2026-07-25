from __future__ import annotations

from inspect import signature

from app.analytics.overview.service import get_analytics_overview


def test_overview_service_accepts_worker_snapshot_hydration_boundary() -> None:
    parameters = signature(get_analytics_overview).parameters

    assert 'hydrate_snapshot_sections' in parameters
    assert 'hydrate_live_sections' not in parameters


def test_overview_service_keeps_top_pods_snapshot_projection() -> None:
    from pathlib import Path

    source = Path('app/analytics/overview/service.py').read_text()

    assert "'pods': _normalize_consumer_items(raw.get('pods', []))" in source
    assert 'get_or_set_cache' not in source


def test_overview_prefers_cluster_with_committed_snapshot(monkeypatch) -> None:
    from app.analytics.overview import service

    class ScalarRows:
        def all(self):
            return ['cluster-b']

    monkeypatch.setattr(
        service.db.session,
        'scalars',
        lambda _statement: ScalarRows(),
    )

    clusters = [
        {'id': 'cluster-a', 'name': 'Cluster A'},
        {'id': 'cluster-b', 'name': 'Cluster B'},
    ]

    selected = service._resolve_selected_cluster(
        clusters=clusters,
        selected_cluster_id=None,
    )

    assert selected == clusters[1]


def test_overview_keeps_explicit_cluster_authoritative(monkeypatch) -> None:
    from app.analytics.overview import service

    def unexpected_scalars(_statement):
        raise AssertionError('explicit cluster selection must not query fallback readiness')

    monkeypatch.setattr(service.db.session, 'scalars', unexpected_scalars)

    clusters = [
        {'id': 'cluster-a', 'name': 'Cluster A'},
        {'id': 'cluster-b', 'name': 'Cluster B'},
    ]

    selected = service._resolve_selected_cluster(
        clusters=clusters,
        selected_cluster_id='cluster-a',
    )

    assert selected == clusters[0]
