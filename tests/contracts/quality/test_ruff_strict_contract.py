from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'
PYPROJECT = ROOT / 'pyproject.toml'
RETIRED = (
    ROOT / 'scripts' / 'verify_ruff_baseline.py',
    ROOT / 'docs' / 'architecture' / 'ruff-debt-baseline.json',
    ROOT / 'tests' / 'contracts' / 'quality' / 'test_ruff_baseline_contract.py',
)


def test_quality_gate_runs_strict_ruff_directly() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')

    assert 'python -m ruff check app migrations tests scripts' in source
    assert 'verify_ruff_baseline.py' not in source


def test_temporary_ruff_baseline_artifacts_are_retired() -> None:
    assert not [str(path.relative_to(ROOT)) for path in RETIRED if path.exists()]


def test_migration_exemptions_remain_narrow() -> None:
    source = PYPROJECT.read_text(encoding='utf-8')

    assert '"migrations/versions/*.py" = ["I001", "UP007", "UP035"]' in source
    assert 'F401' not in source.split('[tool.ruff.lint.per-file-ignores]', 1)[1]
    assert 'F821' not in source.split('[tool.ruff.lint.per-file-ignores]', 1)[1]
