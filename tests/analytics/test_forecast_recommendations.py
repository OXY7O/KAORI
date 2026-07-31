from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = (ROOT / 'app/intelligence/recommendation_engine.py').read_text(encoding='utf-8')


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
    assert "_forecast_review_href(payload, 'trend')" in ENGINE
