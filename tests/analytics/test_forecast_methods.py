from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / 'app/analytics/forecast/service.py'


def load_forecast_helpers() -> dict[str, object]:
    tree = ast.parse(SERVICE.read_text(encoding='utf-8'))
    wanted = {
        'ForecastPoint',
        '_linear_regression',
        '_calculate_signal_quality',
        '_build_forecast_points',
        '_calculate_linear_forecast',
        '_calculate_holt_winters_forecast',
        '_calculate_conservative_forecast',
        '_format_bytes',
        '_format_weekly_trend',
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted
    ]
    module = ast.Module(
        body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes],
        type_ignores=[],
    )
    namespace = {
        'dataclass': dataclass,
        'datetime': datetime,
        'timedelta': timedelta,
        'mean': mean,
        'sqrt': sqrt,
    }
    exec(compile(ast.fix_missing_locations(module), str(SERVICE), 'exec'), namespace)
    return namespace


def make_points(ForecastPoint, count: int = 28):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    seasonal = [0.0, 1.0, 2.0, 1.0, 0.0, -1.0, -2.0]
    return [
        ForecastPoint(start + timedelta(days=index), 20.0 + index * 0.4 + seasonal[index % 7])
        for index in range(count)
    ]


def test_holt_winters_produces_horizon_and_signal_quality() -> None:
    ns = load_forecast_helpers()
    points = make_points(ns['ForecastPoint'])
    result = ns['_calculate_holt_winters_forecast'](values=points, horizon_days=30)
    assert len(result['forecast_points']) == 30
    assert result['latest_daily_average'] == points[-1].value
    assert result['projected_value'] >= 0
    assert result['signal_quality'] in {'High', 'Medium', 'Low'}
    assert 'seasonality' in result['signal_quality_reason'].lower()


def test_conservative_trend_buffers_positive_growth() -> None:
    ns = load_forecast_helpers()
    points = make_points(ns['ForecastPoint'])
    baseline = ns['_calculate_holt_winters_forecast'](values=points, horizon_days=30)
    conservative = ns['_calculate_conservative_forecast'](values=points, horizon_days=30)
    assert conservative['slope_per_day'] >= baseline['slope_per_day']
    assert conservative['projected_value'] >= baseline['latest_daily_average']
    assert '15% buffer' in conservative['signal_quality_reason']


def test_weekly_trend_preserves_negative_direction() -> None:
    ns = load_forecast_helpers()
    assert ns['_format_weekly_trend'](-1024.0, 'bytes').startswith('-')
    assert ns['_format_weekly_trend'](-0.5, 'cores').startswith('-')
    assert ns['_format_weekly_trend'](0.0, 'count') == 'Stable'
