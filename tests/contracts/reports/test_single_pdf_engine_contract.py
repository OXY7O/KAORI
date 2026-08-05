from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_reports_use_one_canonical_weasyprint_engine() -> None:
    artifacts_path = ROOT / 'app' / 'reports' / 'export' / 'artifacts.py'
    service_path = ROOT / 'app' / 'reports' / 'export' / 'service.py'
    artifacts = artifacts_path.read_text()
    service = service_path.read_text()

    assert 'from app.reports.export.html_pdf.renderer import render_weasyprint_pdf' in artifacts
    assert 'FORMAT_PDF: render_weasyprint_pdf' in artifacts
    assert 'get_report_artifact_format' in service
    assert '.renderer(report, staging_path)' in service
    assert 'render_report_pdf' not in service
    assert 'generate_pdf_for_report' not in service


def test_pdf_compatibility_registry_and_old_engine_sources_are_removed() -> None:
    export_root = ROOT / 'app' / 'reports' / 'export'

    assert not (export_root / 'renderers').exists()
    assert not (export_root / 'sections').exists()
    assert not (export_root / 'helpers.py').exists()
    assert not (export_root / 'styles.py').exists()


def test_old_pdf_engine_configuration_and_dependency_are_removed() -> None:
    old_package = 'report' + 'lab'
    old_renderer_setting = 'REPORT_PDF_' + 'RENDERER'
    old_fallback_setting = 'REPORT_PDF_' + 'LEGACY_FALLBACK_ENABLED'

    scanned_files = (
        ROOT / 'requirements' / 'base.in',
        ROOT / 'requirements' / 'base.txt',
        ROOT / '.env.example',
        ROOT / '.env.production.example',
        ROOT / 'app' / 'config' / 'default.py',
        ROOT / 'app' / 'reports' / 'README.md',
        ROOT / 'app' / 'settings' / 'system_information.py',
    )

    for path in scanned_files:
        content = path.read_text().lower()
        assert old_package not in content, path
        assert old_renderer_setting.lower() not in content, path
        assert old_fallback_setting.lower() not in content, path


def test_weasyprint_runtime_is_declared_and_containerized() -> None:
    requirements_input = _read('requirements/base.in')
    requirements_lock = _read('requirements/base.txt')
    dockerfile = _read('Dockerfile')

    assert 'weasyprint==68.0' in requirements_input
    assert 'weasyprint==68.0' in requirements_lock
    for package in (
        'libpango-1.0-0',
        'libpangoft2-1.0-0',
        'libharfbuzz-subset0',
        'libgdk-pixbuf-2.0-0',
    ):
        assert package in dockerfile


def test_pdf_templates_use_the_canonical_local_analytics_publication() -> None:
    component = _read('app/templates/reports/pdf/components/analytics_publication.html')
    unavailable = _read('app/templates/reports/pdf/analytics_unavailable.html')
    css = _read('app/static/reports/pdf/analytics_publication.css')

    assert 'macro report_header' in component
    assert 'macro identity_register' in component
    assert "components/analytics_publication.html" in unavailable
    assert 'http://' not in unavailable
    assert 'https://' not in unavailable
    assert '@page' in css
    assert 'size: A4 portrait' in css
    assert 'table-layout: fixed' in css
    assert 'text-overflow: ellipsis' not in css


def test_single_engine_audit_is_part_of_the_static_quality_gate() -> None:
    quality_gate = _read('scripts/quality_gate.sh')
    audit_script = _read('scripts/verify_single_pdf_engine.py')

    assert 'python scripts/verify_single_pdf_engine.py' in quality_gate
    assert 'one canonical' in audit_script and 'WeasyPrint pipeline' in audit_script
