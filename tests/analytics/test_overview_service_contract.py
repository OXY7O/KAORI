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


def test_snapshot_summary_reports_latest_committed_generation() -> None:
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from app.analytics.overview.snapshot_summary import (
        OVERVIEW_SNAPSHOT_DATASETS,
        present_snapshot_summary,
    )

    now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    snapshots = []
    for index, dataset_key in enumerate(OVERVIEW_SNAPSHOT_DATASETS):
        generated_at = now - timedelta(minutes=20 - index)
        snapshots.append(
            SimpleNamespace(
                dataset_key=dataset_key,
                status='ready',
                generated_at=generated_at,
                expires_at=now + timedelta(minutes=30),
                last_attempt_at=generated_at,
                updated_at=generated_at,
                created_at=generated_at,
            )
        )

    summary = present_snapshot_summary(
        snapshots,
        time_range='24h',
        now=now,
    )

    assert summary['status'] == 'Current'
    assert summary['tone'] == 'normal'
    assert summary['current_dataset_count'] == 7
    assert summary['expected_dataset_count'] == 7
    assert summary['latest_generated_at'] == '2026-07-27 11:46 UTC'
    assert summary['analysis_window'] == 'Last 24 Hours'


def test_snapshot_summary_distinguishes_stale_and_pending_datasets() -> None:
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from app.analytics.overview.snapshot_summary import present_snapshot_summary

    now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    snapshots = [
        SimpleNamespace(
            dataset_key='analytics.utilization.summary',
            status='ready',
            generated_at=now - timedelta(minutes=40),
            expires_at=now - timedelta(minutes=10),
            last_attempt_at=now - timedelta(minutes=40),
            updated_at=now - timedelta(minutes=40),
            created_at=now - timedelta(minutes=40),
        ),
        SimpleNamespace(
            dataset_key='analytics.capacity',
            status='pending',
            generated_at=None,
            expires_at=None,
            last_attempt_at=now - timedelta(minutes=1),
            updated_at=now - timedelta(minutes=1),
            created_at=now - timedelta(minutes=1),
        ),
    ]

    summary = present_snapshot_summary(
        snapshots,
        time_range='7d',
        now=now,
    )

    assert summary['status'] == 'Refresh In Progress'
    assert summary['tone'] == 'info'
    assert summary['stale_dataset_count'] == 1
    assert summary['pending_dataset_count'] == 1
    assert summary['analysis_window'] == 'Last 7 Days'
