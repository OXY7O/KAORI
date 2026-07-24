from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.forecast.service import (
    ForecastPoint,
    _calculate_confidence,
    _calculate_forecast,
    _parse_days,
    _render_namespace_query,
    _resolve_status,
    _select_range_step,
)


def test_forecast_linear_projection_preserves_daily_growth() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    values = [
        ForecastPoint(timestamp=start, value=10.0),
        ForecastPoint(timestamp=start + timedelta(days=1), value=20.0),
    ]

    result = _calculate_forecast(values=values, horizon_days=2, method='linear')

    assert result['current_value'] == 20.0
    assert result['slope_per_day'] == pytest.approx(10.0)
    assert result['projected_value'] == pytest.approx(40.0)
    assert [point.value for point in result['forecast_points']] == pytest.approx([30.0, 40.0])
    assert result['method_label'] == 'Linear Trend'


def test_forecast_namespace_and_option_normalization_is_fail_closed() -> None:
    query = _render_namespace_query(
        namespace='team\\"platform',
        all_query='all',
        namespace_query='metric{namespace="$namespace"}',
    )

    assert query == 'metric{namespace="team\\\\\\"platform"}'
    assert _parse_days('30d', default=7) == 30
    assert _parse_days('invalid', default=7) == 7
    assert _select_range_step(7) == '1h'
    assert _select_range_step(30) == '6h'
    assert _select_range_step(60) == '12h'
    assert _resolve_status(74.9) == 'normal'
    assert _resolve_status(75.0) == 'warning'
    assert _resolve_status(90.0) == 'critical'


def test_forecast_confidence_requires_sufficient_stable_history() -> None:
    assert _calculate_confidence(values=[10.0] * 6, points_count=6)[0] == 'Low'
    assert _calculate_confidence(values=[10.0] * 14, points_count=14)[0] == 'Medium'
    assert _calculate_confidence(values=[10.0] * 30, points_count=30)[0] == 'High'
