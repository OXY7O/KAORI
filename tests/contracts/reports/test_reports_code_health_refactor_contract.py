from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_xlsx_validation_uses_focused_boundary() -> None:
    builder = read('app/reports/export/xlsx/analytics_builder.py')

    expected_import = 'from app.reports.export.xlsx.analytics_validation import validate_analytics_xlsx_artifact'
    assert expected_import in builder
    assert 'def validate_analytics_xlsx_artifact(' not in builder


def test_inventory_xlsx_validation_uses_focused_boundary() -> None:
    builder = read('app/reports/export/xlsx/builder.py')

    expected_import = 'from app.reports.export.xlsx.inventory_validation import validate_inventory_xlsx_artifact'
    assert expected_import in builder
    assert 'def validate_inventory_xlsx_artifact(' not in builder


def test_inventory_xlsx_metadata_rows_use_focused_boundary() -> None:
    builder = read('app/reports/export/xlsx/builder.py')

    expected_import = 'from app.reports.export.xlsx.inventory_metadata import build_inventory_metadata_rows'
    assert expected_import in builder
    assert 'metadata = build_inventory_metadata_rows(dataset, payload)' in builder
    assert "('REPORT IDENTITY', None, None, None)" not in builder


def test_analytics_overview_chart_dispatch_uses_focused_renderers() -> None:
    overview = read('app/reports/export/xlsx/analytics_overview.py')
    chart_dispatch = overview.split('def _add_chart(', 1)[1].split('\n\ndef ', 1)[0]

    for renderer in (
        '_add_comparison_bar_chart',
        '_add_capacity_bar_chart',
        '_add_ranked_bar_chart',
        '_add_composition_bar_chart',
    ):
        assert f'{renderer}(' in chart_dispatch
        assert f'def {renderer}(' in overview

    assert 'visual = BarChart()' not in chart_dispatch


def test_quality_gate_presents_concise_test_evidence() -> None:
    quality_gate = read('scripts/quality_gate.sh')

    assert '--tb=short' in quality_gate
    assert 'PASS — KAORI Functional Tests' in quality_gate
    assert 'FAIL — KAORI Functional Tests' in quality_gate
    assert 'GITHUB_STEP_SUMMARY' in quality_gate
    assert 'pytest -q tests/contracts tests/migrations' in quality_gate
    assert "pytest -q -m 'not debug and not e2e'" in quality_gate
    assert 'pytest -q tests/e2e -m e2e' in quality_gate
