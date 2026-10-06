from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTML_PDF = ROOT / 'app' / 'reports' / 'export' / 'html_pdf'


def test_capacity_refactor_uses_focused_local_package() -> None:
    expected = (
        'capacity/model.py',
        'capacity/charts.py',
        'capacity/forecast.py',
        'capacity/actions.py',
        'capacity/sections.py',
    )
    missing = [relative for relative in expected if not (HTML_PDF / relative).is_file()]
    assert not missing, f'missing Capacity ownership modules: {missing}'


def test_capacity_package_never_imports_facade() -> None:
    package = HTML_PDF / 'capacity'
    assert package.is_dir()
    for path in package.glob('*.py'):
        source = path.read_text()
        assert 'from app.reports.export.html_pdf.capacity_analysis' not in source
        assert 'import app.reports.export.html_pdf.capacity_analysis' not in source


def test_capacity_facade_keeps_symbol() -> None:
    source = (HTML_PDF / 'capacity_analysis.py').read_text()
    assert 'def build_capacity_analysis_presentation(' in source
