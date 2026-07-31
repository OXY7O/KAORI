from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = (ROOT / 'app/analytics/forecast/service.py').read_text(encoding='utf-8')


def test_signal_quality_is_not_named_confidence() -> None:
    assert 'def _calculate_signal_quality(' in SERVICE
    assert "'signal_quality':" in SERVICE
    assert "'signal_quality_reason':" in SERVICE
    assert 'def _calculate_confidence(' not in SERVICE
    assert "'confidence':" not in SERVICE


def test_signal_quality_uses_samples_completeness_and_variation() -> None:
    assert 'expected_days =' in SERVICE
    assert 'completeness =' in SERVICE
    assert 'coefficient_of_variation' in SERVICE
    assert "return 'High'" in SERVICE
    assert "return 'Medium'" in SERVICE
