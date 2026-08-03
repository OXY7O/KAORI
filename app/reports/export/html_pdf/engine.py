from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.document import ReportDocument


def render_document_pdf(
    document: ReportDocument,
    output_path: Path,
    *,
    template_environment: Environment,
    css_path: Path,
    base_url: Path,
    metadata: dict[str, Any] | None = None,
) -> None:
    template = template_environment.get_template(document.template_name)
    rendered_html = template.render(document=document)
    font_config = FontConfiguration()

    specialized_stylesheets = {
        'reports/pdf/analytics_overview.html': 'analytics_overview.css',
        'reports/pdf/resource_utilization.html': 'resource_utilization.css',
        'reports/pdf/capacity_analysis.html': 'capacity_analysis.css',
        'reports/pdf/storage_analysis.html': 'storage_analysis.css',
        'reports/pdf/workload_analysis.html': 'workload_analysis.css',
        'reports/pdf/forecast_analysis.html': 'forecast_analysis.css',
    }
    specialized_stylesheet = specialized_stylesheets.get(document.template_name)
    if specialized_stylesheet:
        # Fixed publication templates are isolated from report.css so generic page,
        # table, and margin-box rules cannot contaminate an approved layout.
        publication_css_path = css_path.with_name(specialized_stylesheet)
        stylesheets = [CSS(filename=str(publication_css_path), font_config=font_config)]
    else:
        stylesheets = [CSS(filename=str(css_path), font_config=font_config)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(
        string=rendered_html,
        base_url=str(base_url),
    ).write_pdf(
        target=str(output_path),
        stylesheets=stylesheets,
        font_config=font_config,
        presentational_hints=True,
        pdf_identifier=(metadata or {}).get('pdf_identifier'),
    )

    if not output_path.exists() or output_path.stat().st_size < 1000:
        raise RuntimeError('WeasyPrint did not produce a valid PDF artifact.')

    with output_path.open('rb') as handle:
        if handle.read(5) != b'%PDF-':
            raise RuntimeError('WeasyPrint output is not a PDF document.')
