from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / 'app/intelligence/recommendation_engine.py'
ENGINE = ENGINE_PATH.read_text(encoding='utf-8')


def _load_recommendation_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        'forecast_recommendation_engine',
        ENGINE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recommendations_use_factual_forecast_terms() -> None:
    assert "item.get('latest_daily_average_percent'" in ENGINE
    assert "item.get('weekly_trend'" in ENGINE
    assert "item.get('signal_quality'" in ENGINE
    assert 'Current usage is' not in ENGINE
    assert 'forecast_confidence' not in ENGINE


def test_recommendations_link_to_resource_or_trend_tabs() -> None:
    assert "def _forecast_review_href" in ENGINE
    assert "'tab': tab" in ENGINE
    assert "resource_key if resource_key in {'cpu', 'memory', 'storage', 'pods'} else 'trend'" in ENGINE
    assert "trend_href = _forecast_review_href(payload, 'trend')" in ENGINE


def test_forecast_baseline_recommendations_have_initialized_trend_href() -> None:
    engine = _load_recommendation_module()

    recommendations = engine.build_forecast_actionable_recommendations(
        {
            'items': [],
            'summary': {},
            'namespace': 'payments',
            'forecast_method': 'holt_winters',
            'history_window': '30d',
            'forecast_horizon': '90d',
        }
    )

    assert [item['source'] for item in recommendations] == [
        'forecast_baseline',
        'forecast_practice',
    ]
    assert all(item['href'].startswith('/analytics/forecast?tab=trend&') for item in recommendations)
    assert all('namespace=payments' in item['href'] for item in recommendations)
    assert all(item['is_actionable'] == 'No' for item in recommendations)
