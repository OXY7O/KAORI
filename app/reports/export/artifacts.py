from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.reports.catalog import FORMAT_CSV, FORMAT_PDF, FORMAT_XLSX, OUTPUT_FORMAT_SPECS
from app.reports.export.csv.renderer import render_report_csv
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


_RENDERERS: dict[str, Callable[['Report', Path], None]] = {
    FORMAT_PDF: render_weasyprint_pdf,
    FORMAT_XLSX: render_inventory_xlsx,
    FORMAT_CSV: render_report_csv,
}

REPORT_ARTIFACT_FORMATS: dict[str, ReportArtifactFormat] = {
    value: ReportArtifactFormat(
        value=spec.value,
        label=spec.label,
        extension=spec.extension,
        mimetype=spec.mimetype,
        renderer=_RENDERERS[value],
    )
    for value, spec in OUTPUT_FORMAT_SPECS.items()
}


def get_report_artifact_format(value: str | None) -> ReportArtifactFormat:
    normalized = str(value or '').strip().lower()
    try:
        return REPORT_ARTIFACT_FORMATS[normalized]
    except KeyError as exc:
        raise ValueError(f'Unsupported report output format: {normalized or "empty"}.') from exc
