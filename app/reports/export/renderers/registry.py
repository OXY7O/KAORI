from __future__ import annotations

from pathlib import Path

from flask import current_app

from app.models.report import Report

_SUPPORTED_RENDERERS = {'weasyprint', 'reportlab'}


def get_configured_renderer_name() -> str:
    configured = str(current_app.config.get('REPORT_PDF_RENDERER', 'weasyprint')).strip().lower()
    return configured if configured in _SUPPORTED_RENDERERS else 'weasyprint'


def get_configured_renderer_label() -> str:
    return 'WeasyPrint HTML/PDF' if get_configured_renderer_name() == 'weasyprint' else 'ReportLab Legacy'


def render_report_pdf(report: Report, output_path: Path) -> str:
    renderer_name = get_configured_renderer_name()
    fallback_enabled = bool(current_app.config.get('REPORT_PDF_LEGACY_FALLBACK_ENABLED', True))

    if renderer_name == 'reportlab':
        _render_reportlab(report, output_path)
        return 'reportlab'

    try:
        from app.reports.export.html_pdf.renderer import render_weasyprint_pdf

        render_weasyprint_pdf(report, output_path)
        return 'weasyprint'
    except Exception:
        current_app.logger.exception(
            'WeasyPrint report rendering failed for report %s.',
            getattr(report, 'id', 'unknown'),
        )
        if not fallback_enabled:
            raise
        _render_reportlab(report, output_path)
        return 'reportlab-fallback'


def _render_reportlab(report: Report, output_path: Path) -> None:
    from app.reports.export.service import render_reportlab_pdf

    render_reportlab_pdf(report, output_path)
