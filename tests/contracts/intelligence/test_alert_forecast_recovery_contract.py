from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_missing_forecast_rule_requires_a_fresh_ready_snapshot() -> None:
    source = (ROOT / 'app/intelligence/alert_intelligence/recommendation_source.py').read_text(encoding='utf-8')
    assert "rule_key.startswith('object_storage.forecast.')" in source
    assert "ObjectStorageForecastSnapshot.status == 'ready'" in source
    assert 'ObjectStorageForecastSnapshot.expires_at > datetime.now(UTC)' in source
    assert "for key in ('days_to_capacity', 'growth_per_day')" in source
    assert "return False, 'source_unavailable'" in source
