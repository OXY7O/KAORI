from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_type_safety_verifier_owns_canonical_forecast_recommendation_boundary() -> None:
    verifier = read('scripts/verify_pre_release_type_safety.py')
    forecast = read('app/kubernetes/analytics/forecast/presentation.py')

    assert "'actionable_recommendations = ['" in verifier
    assert 'forecast recommendation normalization' in verifier
    assert "_as_list(forecast_payload.get('actionable_recommendations'))" in forecast
    assert 'if isinstance(item, dict)' in forecast
    assert "'recommendation_count': count_actionable_recommendations(actionable_recommendations)" in forecast
    assert "actionable_recommendations = forecast_payload.get('actionable_recommendations')" not in verifier


def test_type_safety_verifier_uses_short_kaori_success_title() -> None:
    verifier = read('scripts/verify_pre_release_type_safety.py')

    assert "print('PASS — KAORI Type Safety')" in verifier
    assert 'pre-release type-safety contract passed' not in verifier


def test_general_release_runner_suppresses_success_chatter_on_failure() -> None:
    runner = read('scripts/verify_final_release.py')

    assert 'def _is_success_chatter(line: str) -> bool:' in runner
    assert "stripped.startswith('PASS — KAORI ')" in runner
    assert 'def _failure_output(stdout: str, stderr: str) -> str:' in runner
    assert "stripped.startswith('[KAORI hygiene] tracked source is clean')" in runner
    assert "stripped in {'All checks passed!', 'Checking formatting...'}" in runner
    assert "' are valid'" in runner
    assert "' is acyclic'" in runner
    assert "' is closed'" in runner
    assert 'output = _failure_output(result.stdout, result.stderr)' in runner
    assert runner.index('from release_surface_registry import SURFACES') < runner.index(
        'sys.dont_write_bytecode = True'
    )
