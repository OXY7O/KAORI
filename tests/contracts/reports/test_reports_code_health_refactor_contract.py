from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_xlsx_validation_uses_focused_boundary() -> None:
    builder = read('app/reports/export/xlsx/analytics_builder.py')

    expected_import = (
        'from app.reports.export.xlsx.analytics_validation import '
        'validate_analytics_xlsx_artifact'
    )
    assert expected_import in builder
    assert 'def validate_analytics_xlsx_artifact(' not in builder


def test_inventory_xlsx_validation_uses_focused_boundary() -> None:
    builder = read('app/reports/export/xlsx/builder.py')

    expected_import = (
        'from app.reports.export.xlsx.inventory_validation import '
        'validate_inventory_xlsx_artifact'
    )
    assert expected_import in builder
    assert 'def validate_inventory_xlsx_artifact(' not in builder


def test_quality_gate_presents_concise_test_evidence() -> None:
    quality_gate = read('scripts/quality_gate.sh')

    assert '--tb=short' in quality_gate
    assert 'PASS — KAORI Functional Tests' in quality_gate
    assert 'FAIL — KAORI Functional Tests' in quality_gate
    assert 'GITHUB_STEP_SUMMARY' in quality_gate
    assert 'pytest -q tests/e2e -m e2e' in quality_gate
