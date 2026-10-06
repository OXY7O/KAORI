from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CALCULATION = (ROOT / 'app/kubernetes/analytics/forecast/calculation.py').read_text(encoding='utf-8')


def test_signal_quality_is_not_named_confidence() -> None:
    assert 'def _calculate_signal_quality(' in CALCULATION
    assert "'signal_quality':" in CALCULATION
    assert "'signal_quality_reason':" in CALCULATION
    assert 'def _calculate_confidence(' not in CALCULATION
    assert "'confidence':" not in CALCULATION


def test_signal_quality_uses_samples_completeness_and_variation() -> None:
    assert 'expected_days =' in CALCULATION
    assert 'completeness =' in CALCULATION
    assert 'coefficient_of_variation' in CALCULATION
    assert "return 'High'" in CALCULATION
    assert "return 'Medium'" in CALCULATION


def test_threshold_eta_uses_projected_points_and_selected_horizon() -> None:
    assert 'def _calculate_threshold_eta(' in CALCULATION
    assert "f'Beyond {horizon_days}d horizon'" in CALCULATION
    assert 'for point in forecast_points:' in CALCULATION
    assert (
        'slope_per_day'
        not in CALCULATION.split('def _calculate_threshold_eta', 1)[1].split('def _resolve_summary_posture', 1)[0]
    )
