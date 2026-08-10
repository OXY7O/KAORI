from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.analytics.forecast.calculation import (
    _calculate_conservative_forecast,
    _calculate_holt_winters_forecast,
    _format_weekly_trend,
)
from app.analytics.forecast.contracts import ForecastPoint


def make_points(count: int = 28) -> list[ForecastPoint]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    seasonal = [0.0, 1.0, 2.0, 1.0, 0.0, -1.0, -2.0]
    return [
        ForecastPoint(start + timedelta(days=index), 20.0 + index * 0.4 + seasonal[index % 7]) for index in range(count)
    ]


def test_holt_winters_produces_horizon_and_signal_quality() -> None:
    points = make_points()
    result = _calculate_holt_winters_forecast(values=points, horizon_days=30)
    assert len(result['forecast_points']) == 30
    assert result['latest_daily_average'] == points[-1].value
    assert result['projected_value'] >= 0
    assert result['signal_quality'] in {'High', 'Medium', 'Low'}
    assert 'seasonality' in result['signal_quality_reason'].lower()


def test_conservative_trend_buffers_positive_growth_and_preserves_horizon() -> None:
    points = make_points()
    baseline = _calculate_holt_winters_forecast(values=points, horizon_days=30)
    conservative = _calculate_conservative_forecast(values=points, horizon_days=30)
    assert len(conservative['forecast_points']) == len(baseline['forecast_points']) == 30
    assert conservative['projected_value'] >= baseline['latest_daily_average']
    assert conservative['projected_value'] >= baseline['projected_value']
    assert '15% uplift' in conservative['signal_quality_reason']


def test_weekly_trend_preserves_negative_direction() -> None:
    assert _format_weekly_trend(-1024.0, 'bytes').startswith('-')
    assert _format_weekly_trend(-0.5, 'cores').startswith('-')
    assert _format_weekly_trend(0.0, 'count') == 'Stable'
