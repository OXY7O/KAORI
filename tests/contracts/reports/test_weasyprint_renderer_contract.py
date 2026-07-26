from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_weasyprint_is_configured_with_legacy_fallback() -> None:
    config = (ROOT / 'app' / 'config' / 'default.py').read_text()
    registry = (ROOT / 'app' / 'reports' / 'export' / 'renderers' / 'registry.py').read_text()

    assert "'REPORT_PDF_RENDERER'" in config
    assert "'weasyprint'" in config
    assert "'REPORT_PDF_LEGACY_FALLBACK_ENABLED'" in config
    assert 'render_weasyprint_pdf' in registry
    assert 'render_reportlab_pdf' in registry


def test_container_and_requirements_include_weasyprint_runtime() -> None:
    requirements = (ROOT / 'requirements' / 'base.txt').read_text()
    dockerfile = (ROOT / 'Dockerfile').read_text()

    assert 'weasyprint==68.0' in requirements
    for package in (
        'libpango-1.0-0',
        'libpangoft2-1.0-0',
        'libharfbuzz-subset0',
        'libgdk-pixbuf-2.0-0',
    ):
        assert package in dockerfile


def test_pdf_template_uses_local_assets_and_template_sections() -> None:
    template = (ROOT / 'app' / 'templates' / 'reports' / 'pdf' / 'report.html').read_text()
    css = (ROOT / 'app' / 'static' / 'reports' / 'pdf' / 'report.css').read_text()

    assert 'for section in document.sections' in template
    assert 'target-counter(attr(href), page)' in css
    assert 'counter(pages)' in css
    assert 'http://' not in template
    assert 'https://' not in template
    assert '@page cover' in css
