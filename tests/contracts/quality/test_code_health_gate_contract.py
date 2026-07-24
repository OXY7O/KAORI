from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'
VERIFIER = ROOT / 'scripts' / 'verify_code_health.py'
BASELINE = ROOT / 'docs' / 'architecture' / 'code-health-debt-baseline.json'


def test_quality_gate_bounds_maintainability_debt() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    assert 'python scripts/verify_code_health.py' in source
    assert VERIFIER.exists()
    assert BASELINE.exists()


def test_code_health_gate_covers_primary_debt_dimensions() -> None:
    source = VERIFIER.read_text(encoding='utf-8')
    for token in (
        'module_line_limits',
        'function_line_limits',
        'function_branch_limits',
        'function_argument_limits',
        'broad_exception_limit',
    ):
        assert token in source
