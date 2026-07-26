from __future__ import annotations

from pathlib import Path

from flask import current_app

from app.models.report import Report
from app.reports.export.html_pdf.builder import build_report_document
from app.reports.export.html_pdf.collectors import collect_report_payload
from app.reports.export.html_pdf.engine import render_document_pdf


def render_weasyprint_pdf(report: Report, output_path: Path) -> None:
    payload = collect_report_payload(report)
    document = build_report_document(
        report,
        payload,
        classification=str(current_app.config.get('REPORT_PDF_CLASSIFICATION', 'Internal')),
        retention_days=int(current_app.config.get('REPORT_RETENTION_DAYS', 90) or 90),
    )

    project_root = Path(current_app.root_path).parent
    css_path = Path(current_app.root_path) / 'static' / 'reports' / 'pdf' / 'report.css'

    render_document_pdf(
        document,
        output_path,
        template_environment=current_app.jinja_env,
        css_path=css_path,
        base_url=project_root,
        metadata={'pdf_identifier': f'kaori-report-{report.id}'},
    )
