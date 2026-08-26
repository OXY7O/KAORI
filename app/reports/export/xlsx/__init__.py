"""Reusable KAORI Inventory Excel export package.

Keep the renderer import lazy. ``inventory_common`` depends on the workbook
profile definitions in :mod:`app.reports.export.xlsx.standard`, while the
renderer itself depends on ``inventory_common``. Eagerly importing the renderer
from this package initializer would therefore create a circular import whenever
``xlsx.standard`` is imported.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.reports.export.xlsx.standard import (
    INVENTORY_WORKBOOK_STANDARD,
    INVENTORY_XLSX_REPORT_TYPES,
    XLSX_REPORTING_STANDARD,
    get_inventory_workbook_profile,
)

if TYPE_CHECKING:
    from app.models.report import Report


def render_inventory_xlsx(report: Report, output_path: Path) -> None:
    """Render an Inventory workbook without eager-loading the renderer module."""

    from app.reports.export.xlsx.renderer import render_inventory_xlsx as _render_inventory_xlsx

    _render_inventory_xlsx(report, output_path)


__all__ = [
    'INVENTORY_WORKBOOK_STANDARD',
    'INVENTORY_XLSX_REPORT_TYPES',
    'XLSX_REPORTING_STANDARD',
    'get_inventory_workbook_profile',
    'render_inventory_xlsx',
]
