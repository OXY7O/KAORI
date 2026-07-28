from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_live_and_materialized_presenters_expose_stable_hero_counters():
    source = read('app/analytics/alerts/application.py')
    assert 'def _summary_aliases(' in source
    assert source.count('**_summary_aliases(summary),') == 2
    for key in ('active_alerts', 'critical_alerts', 'warning_alerts', 'anomaly_count'):
        assert f"'{key}':" in source


def test_alert_hero_has_safe_summary_fallbacks_for_legacy_snapshots():
    source = read('app/templates/analytics/alerts/partials/_hero.html')
    assert "{% set hero_summary = summary|default({}, true) %}" in source
    assert "hero_summary.get('active_alerts', 0)" in source
    assert "hero_summary.get('critical_alerts', 0)" in source
    assert "hero_summary.get('warning_alerts', 0)" in source
    assert "hero_summary.get('detected_anomalies', 0)" in source
