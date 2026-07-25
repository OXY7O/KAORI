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
