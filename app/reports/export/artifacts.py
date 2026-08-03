from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.reports.export.html_pdf.renderer import render_weasyprint_pdf
from app.reports.export.xlsx.renderer import render_inventory_xlsx

if TYPE_CHECKING:
    from app.models.report import Report


@dataclass(frozen=True, slots=True)
class ReportArtifactFormat:
    value: str
    label: str
    extension: str
    mimetype: str
    renderer: Callable[['Report', Path], None]


REPORT_ARTIFACT_FORMATS: dict[str, ReportArtifactFormat] = {
    'pdf': ReportArtifactFormat(
        value='pdf',
        label='PDF',
        extension='.pdf',
        mimetype='application/pdf',
        renderer=render_weasyprint_pdf,
    ),
    'xlsx': ReportArtifactFormat(
        value='xlsx',
        label='Excel Workbook',
        extension='.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        renderer=render_inventory_xlsx,
    ),
}


def get_report_artifact_format(value: str | None) -> ReportArtifactFormat:
    normalized = str(value or 'pdf').strip().lower()
    try:
        return REPORT_ARTIFACT_FORMATS[normalized]
    except KeyError as exc:
        raise ValueError(f'Unsupported report output format: {normalized}.') from exc
