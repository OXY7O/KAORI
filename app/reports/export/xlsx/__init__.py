"""Reusable KAORI XLSX export contracts for Inventory and Analytics.

Keep renderer imports lazy. Inventory collection depends on the workbook profile
registry, while the family-aware renderer depends on both Inventory and
Analytics builders. Eager renderer imports here would create circular imports
for callers that only need XLSX contract/profile definitions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.reports.export.xlsx.analytics_profiles import (
    ANALYTICS_XLSX_REPORT_TYPES,
    get_analytics_workbook_profile,
)
from app.reports.export.xlsx.analytics_schema import ANALYTICS_WORKBOOK_STANDARD
from app.reports.export.xlsx.standard import (
    INVENTORY_WORKBOOK_STANDARD,
    INVENTORY_XLSX_REPORT_TYPES,
    XLSX_REPORTING_STANDARD,
    get_inventory_workbook_profile,
)

if TYPE_CHECKING:
    from app.models.report import Report


def render_report_xlsx(report: Report, output_path: Path) -> None:
    """Render an XLSX artifact through the canonical family-aware renderer."""

    from app.reports.export.xlsx.renderer import render_report_xlsx as _render_report_xlsx

    _render_report_xlsx(report, output_path)


def render_inventory_xlsx(report: Report, output_path: Path) -> None:
    """Render an Inventory workbook without eager-loading the renderer module."""

    from app.reports.export.xlsx.renderer import render_inventory_xlsx as _render_inventory_xlsx

    _render_inventory_xlsx(report, output_path)


__all__ = [
    'ANALYTICS_WORKBOOK_STANDARD',
    'ANALYTICS_XLSX_REPORT_TYPES',
    'INVENTORY_WORKBOOK_STANDARD',
    'INVENTORY_XLSX_REPORT_TYPES',
    'XLSX_REPORTING_STANDARD',
    'get_analytics_workbook_profile',
    'get_inventory_workbook_profile',
    'render_inventory_xlsx',
    'render_report_xlsx',
]
