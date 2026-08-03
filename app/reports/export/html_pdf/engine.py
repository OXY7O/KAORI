from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_SHARED_STYLESHEET,
    ANALYTICS_TEMPLATE_STYLESHEETS,
)
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

    fixed_publication_stylesheets = {
        'reports/pdf/tls_certificate_health.html': 'tls_certificate_health.css',
        'reports/pdf/inventory_overview.html': 'inventory_publications.css',
        'reports/pdf/nodes_inventory.html': 'inventory_publications.css',
        'reports/pdf/namespaces_inventory.html': 'inventory_publications.css',
        'reports/pdf/workloads_inventory.html': 'inventory_publications.css',
        'reports/pdf/pods_inventory.html': 'inventory_publications.css',
        'reports/pdf/services_inventory.html': 'inventory_publications.css',
        'reports/pdf/ingresses_inventory.html': 'inventory_publications.css',
        'reports/pdf/storage_inventory.html': 'inventory_publications.css',
        'reports/pdf/topology_inventory.html': 'inventory_publications.css',
    }

    analytics_stylesheet = ANALYTICS_TEMPLATE_STYLESHEETS.get(document.template_name)
    fixed_stylesheet = fixed_publication_stylesheets.get(document.template_name)

    if analytics_stylesheet:
        # Analytics reports use one canonical publication grammar derived from
        # Analytics Overview Report ID 34. Report-specific CSS is loaded first;
        # the Analytics standard is loaded last and owns reusable primitives.
        report_css_path = css_path.with_name(analytics_stylesheet)
        analytics_css_path = css_path.with_name(ANALYTICS_SHARED_STYLESHEET)
        stylesheets = [
            CSS(filename=str(report_css_path), font_config=font_config),
            CSS(filename=str(analytics_css_path), font_config=font_config),
        ]
    elif fixed_stylesheet:
        # Existing non-Analytics fixed publications remain isolated from the
        # Analytics contract until their own output family is implemented.
        report_css_path = css_path.with_name(fixed_stylesheet)
        shared_css_path = css_path.with_name('kaori_publication.css')
        stylesheets = [
            CSS(filename=str(report_css_path), font_config=font_config),
            CSS(filename=str(shared_css_path), font_config=font_config),
        ]
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
