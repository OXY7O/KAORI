from __future__ import annotations

from pathlib import Path

from app.models.report import Report
from app.reports.catalog import FORMAT_XLSX, validate_report_instance
from app.reports.export.inventory_common import (
    build_inventory_export_context,
    collect_inventory_payload,
)
from app.reports.export.xlsx.builder import build_inventory_workbook
from app.reports.export.xlsx.standard import INVENTORY_XLSX_REPORT_TYPES


def render_inventory_xlsx(report: Report, output_path: Path) -> None:
    validate_report_instance(report)
    if report.output_format != FORMAT_XLSX:
        raise ValueError('The canonical Excel renderer accepts XLSX reports only.')
    if report.report_type not in INVENTORY_XLSX_REPORT_TYPES:
        raise ValueError(f'Report type {report.report_type!r} is not an Inventory Excel report.')

    payload = collect_inventory_payload(report)
    error = str(payload.get('_error') or '').strip()
    if error:
        raise RuntimeError(error)

    build_inventory_workbook(
        report_type=report.report_type,
        payload=payload,
        context=build_inventory_export_context(report, payload),
        output_path=output_path,
    )
