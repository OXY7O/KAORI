"""Regression guard for KAORI Capacity Analysis Evidence Boundary layout."""

from pathlib import Path


def load_capacity_analysis_template() -> str:
    path = Path("app/templates/reports/pdf/capacity_analysis.html")
    return path.read_text(encoding="utf-8")


def load_capacity_analysis_css() -> str:
    path = Path("app/static/reports/pdf/capacity_analysis.css")
    return path.read_text(encoding="utf-8")


def test_capacity_evidence_boundary_uses_two_columns():
    html = load_capacity_analysis_template()

    assert 'boundary-columns boundary-columns--capacity' in html
    assert 'Included in This Report' in html
    assert 'Not Included in This Report' in html


def test_capacity_evidence_boundary_column_styles_are_present():
    css = load_capacity_analysis_css()

    assert '.boundary-columns--capacity' in css
    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)' in css
    assert 'column-gap: 14mm' in css
    assert 'align-items: start' in css
