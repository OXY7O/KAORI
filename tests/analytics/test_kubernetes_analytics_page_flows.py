from __future__ import annotations

from pathlib import Path


def test_all_analytics_presenters_remain_importable() -> None:
    from app.analytics.kubernetes.alerts.application import present_alerts_materialized_context
    from app.analytics.kubernetes.capacity.presentation import present_capacity_context
    from app.analytics.kubernetes.forecast.presentation import present_forecast_materialized_context
    from app.analytics.kubernetes.storage.presentation import present_storage_materialized_context
    from app.analytics.kubernetes.top_consumers.presentation import (
        present_materialized_context as present_top_consumers_context,
    )
    from app.analytics.kubernetes.workload.presentation import present_workload_materialized_context

    assert callable(present_alerts_materialized_context)
    assert callable(present_capacity_context)
    assert callable(present_forecast_materialized_context)
    assert callable(present_storage_materialized_context)
    assert callable(present_top_consumers_context)
    assert callable(present_workload_materialized_context)


def test_user_facing_analytics_routes_do_not_query_providers_directly() -> None:
    route_files = [
        Path('app/analytics/routes.py'),
        *Path('app/analytics').glob('*/routes.py'),
    ]
    forbidden = (
        'MetricsService',
        'MetricsConsumer',
        'load_alerts_by_source',
        'get_alertmanager_alerts',
        '.query_range(',
    )

    for path in route_files:
        source = path.read_text()
        for token in forbidden:
            assert token not in source, f'{path} executes provider work through {token}'


def test_pending_workspace_reports_worker_progress_without_aggressive_polling() -> None:
    source = Path('app/templates/analytics/kubernetes/materialization/_pending.html').read_text()

    assert 'hx-trigger="every 5s"' in source
    assert 'materialization_progress_message' in source
    assert 'materialization_progress_percent' in source
