"""Reusable KAORI CSV export package with a lazy renderer boundary."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.report import Report


def render_report_csv(report: Report, output_path: Path) -> None:
    """Render CSV without importing the full report pipeline at package import time."""

    from app.reports.export.csv.renderer import render_report_csv as _render_report_csv

    _render_report_csv(report, output_path)


__all__ = ['render_report_csv']
