from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_reports_use_one_canonical_weasyprint_engine() -> None:
    registry_path = ROOT / 'app' / 'reports' / 'export' / 'artifacts.py'
    registry = registry_path.read_text()
    registry_module = ast.parse(registry)

    imported_names = {
        alias.name
        for node in ast.walk(registry_module)
        if isinstance(node, ast.ImportFrom)
        and node.module == 'app.reports.export.html_pdf.renderer'
        for alias in node.names
    }

    service_path = ROOT / 'app' / 'reports' / 'export' / 'service.py'
    service = service_path.read_text()
    service_module = ast.parse(service)
    service_imports = {
        alias.name
        for node in ast.walk(service_module)
        if isinstance(node, ast.ImportFrom)
        and node.module == 'app.reports.export.artifacts'
        for alias in node.names
    }
    function_names = {
        node.name
        for node in service_module.body
        if isinstance(node, ast.FunctionDef)
    }

    assert 'render_weasyprint_pdf' in imported_names
    assert 'FORMAT_PDF: render_weasyprint_pdf' in registry
    assert 'get_report_artifact_format' in service_imports
    old_wrapper = 'render_' + 'report_pdf'
    old_label_helper = 'format_' + 'renderer_label'
    assert old_wrapper not in function_names
    assert old_label_helper not in function_names


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


def test_pdf_template_uses_local_assets_and_template_sections() -> None:
    template = _read('app/templates/reports/pdf/report.html')
    css = _read('app/static/reports/pdf/report.css')

    assert 'for section in document.sections' in template
    assert 'target-counter(attr(href), page)' in css
    assert 'counter(pages)' in css
    assert 'http://' not in template
    assert 'https://' not in template
    assert '@page cover' in css


def test_single_engine_audit_is_part_of_the_static_quality_gate() -> None:
    quality_gate = _read('scripts/quality_gate.sh')
    audit_script = _read('scripts/verify_single_pdf_engine.py')

    assert 'python scripts/verify_single_pdf_engine.py' in quality_gate
    assert 'one canonical ' in audit_script
    assert 'WeasyPrint pipeline' in audit_script


def test_report_runtime_import_audit_is_part_of_the_static_quality_gate() -> None:
    quality_gate = _read('scripts/quality_gate.sh')
    runtime_audit = _read('scripts/verify_report_runtime_imports.py')

    assert 'python scripts/verify_report_runtime_imports.py' in quality_gate
    assert 'from app.reports.export.artifacts import get_report_artifact_format' in runtime_audit
    assert 'without circular imports' in runtime_audit
