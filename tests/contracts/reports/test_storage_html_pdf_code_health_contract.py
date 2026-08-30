from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTML_PDF = ROOT / 'app' / 'reports' / 'export' / 'html_pdf'


def test_storage_refactor_uses_focused_local_package() -> None:
    expected = (
        'storage/model.py',
        'storage/records.py',
        'storage/trend.py',
        'storage/actions.py',
        'storage/sections.py',
    )
    missing = [relative for relative in expected if not (HTML_PDF / relative).is_file()]
    assert not missing, f'missing Storage ownership modules: {missing}'


def test_storage_package_never_imports_facade() -> None:
    package = HTML_PDF / 'storage'
    assert package.is_dir()
    for path in package.glob('*.py'):
        source = path.read_text(encoding='utf-8')
        assert 'from app.reports.export.html_pdf.storage_analysis' not in source
        assert 'import app.reports.export.html_pdf.storage_analysis' not in source


def test_storage_facade_keeps_symbol() -> None:
    source = (HTML_PDF / 'storage_analysis.py').read_text(encoding='utf-8')
    assert 'def build_storage_analysis_presentation(' in source
